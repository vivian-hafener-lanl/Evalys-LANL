# coding: utf-8

from __future__ import unicode_literals, print_function

import matplotlib
import matplotlib.dates
import matplotlib.patches as mpatch
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import random

from . import core
from .. import metrics


available_series = ["bonded_slowdown", "waiting_time", "all"]


def annotate(ax, rect, annot):
    rx, ry = rect.get_xy()
    cx = rx + rect.get_width() / 2.0
    cy = ry + rect.get_height() / 2.0

    ax.annotate(
        annot, (cx, cy), color="black", fontsize="small", ha="center", va="center"
    )


def map_unique_numbers(df):
    """Map the DataFrame of jobs to a set of jobs which should be labeled and a list of unique ids
    for the given DataFrame.

    Jobs which have the same jobID and workload_name will be merged together and the same
    unique_id will be assigned to them. The set of labeled_jobs will only contain the job
    in the middle of each list of jobs sharing the same id.
    """
    labeled_jobs = set()
    unique_numbers = []

    # Jobs start their number with 1
    number_counter = 1
    numbers_map = {}
    jobs_for_unique_number = {}

    for index, row in df.iterrows():
        workload_name = str(row["workload_name"])
        job_id = str(row["jobID"])
        full_job_id = workload_name + "!" + job_id
        job_intervals = row["allocated_resources"]

        try:
            # The job id was already in the workload: re-use the same unique id.
            unique_number = numbers_map[full_job_id]
            list_of_jobs = jobs_for_unique_number[full_job_id]
        except KeyError:
            # The job id is new: generate a new unique number for this
            # workload_name!jobID combination.
            unique_number = number_counter
            numbers_map[full_job_id] = number_counter
            number_counter += 1
            jobs_for_unique_number[full_job_id] = list_of_jobs = []

        if job_intervals:
            list_of_jobs.append((index, row))

        unique_numbers.append(unique_number)

    for k, v in jobs_for_unique_number.items():
        # If there are jobs for this job id which have job intervals:
        # search for the element in the middle and add its index to the set.
        if v:
            index, row = v[len(v) // 2]
            labeled_jobs.add(index)

    return labeled_jobs, unique_numbers


def plot_gantt(
    jobset,
    ax=None,
    title="Gantt chart",
    labels=True,
    palette=None,
    alpha=0.4,
    time_scale=False,
    color_function=None,
    label_function=None,
    resvStart=None,
    resvExecTime=None,
    resvNodes=None,
    windowStartTime=None,
    windowFinishTime=None,
):
    # Palette generation if needed
    if palette is None:
        palette = core.generate_palette(8)
    assert len(palette) > 0

    if color_function is None:

        def color_randrobin_select(job, palette):
            return palette[job.unique_number % len(palette)]

        color_function = color_randrobin_select
    if label_function is None:

        def job_id_label(job):
            return job["jobID"]

        label_function = job_id_label

    # Get current axe to plot
    if ax is None:
        ax = plt.gca()

    df = jobset.df.copy()
    labeled_jobs, unique_numbers = map_unique_numbers(df)
    df["unique_number"] = unique_numbers

    if time_scale:
        df["submission_time"] = pd.to_datetime(df["submission_time"], unit="s")
        df["starting_time"] = pd.to_datetime(df["starting_time"], unit="s")
        df["execution_time"] = pd.to_timedelta(df["execution_time"], unit="s")

    def plot_job(job):
        col = color_function(job, palette)
        duration = job["execution_time"]
        for itv in job["allocated_resources"].intervals():
            (y0, y1) = itv
            x0 = job["starting_time"]
            if time_scale:
                # Convert date to matplotlib float representation
                x0 = matplotlib.dates.date2num(x0.to_pydatetime())
                finish_time = matplotlib.dates.date2num(
                    job["starting_time"] + job["execution_time"]
                )
                duration = finish_time - x0
            rect = mpatch.Rectangle(
                (x0, y0),
                duration,
                y1 - y0 + 0.9,
                alpha=alpha,
                facecolor=col,
                edgecolor="black",
                linewidth=0.5,
            )
            if labels:
                if job.name in labeled_jobs:
                    annotate(ax, rect, str(label_function(job)))
            ax.add_artist(rect)

    if resvStart != None and resvExecTime != None:
        resvNodes = str(resvNodes)
        resvNodes = resvNodes.split("-")
        startNode = int(resvNodes[0])
        height = int(resvNodes[1]) - int(resvNodes[0])
        rect = matplotlib.patches.Rectangle(
            (resvStart, startNode),
            resvExecTime,
            height,
            alpha=alpha,
            facecolor="#FF0000",
            edgecolor="black",
            linewidth=0.5,
        )
        ax.add_artist(rect)

    # apply for all jobs
    df.apply(plot_job, axis=1)

    # set graph limits, grid and title
    if not windowStartTime and not windowFinishTime:
        ax.set_xlim(
            df["submission_time"].min(),
            (df["starting_time"] + df["execution_time"]).max(),
        )
    elif windowStartTime and windowFinishTime:
        ax.set_xlim(windowStartTime, windowFinishTime)
    ax.set_ylim(jobset.res_bounds[0] - 1, jobset.res_bounds[1] + 2)
    ax.grid(True)
    ax.set_title(title)
    ax.set_ylabel("Machines")


def plot_pstates(
    pstates,
    x_horizon,
    ax=None,
    palette=None,
    off_pstates=None,
    son_pstates=None,
    soff_pstates=None,
):
    # palette generation if needed
    if palette is None:
        palette = ["#000000", "#56ae6c", "#ba495b"]
    assert len(palette) >= 3
    labels = ["OFF", "switch ON", "switch OFF"]
    alphas = [0.6, 1, 1]

    if off_pstates is None:
        off_pstates = set()
    if son_pstates is None:
        son_pstates = set()
    if soff_pstates is None:
        soff_pstates = set()
    # Get current axe to plot
    if ax is None:
        ax = plt.gca()

    interesting_pstates = off_pstates | son_pstates | soff_pstates

    for _, job in pstates.pseudo_jobs.iterrows():
        if job["pstate"] in interesting_pstates:
            if job["pstate"] in off_pstates:
                col_id = 0
            elif job["pstate"] in son_pstates:
                col_id = 1
            elif job["pstate"] in soff_pstates:
                col_id = 2

            color = palette[col_id]
            alpha = alphas[col_id]
            label = labels[col_id]

            interval_list = pstates.intervals[job["interval_id"]]
            for machine_interval in interval_list:
                (y0, y1) = machine_interval
                (b, e) = (job["begin"], min(job["end"], x_horizon))
                rect = mpatch.Rectangle(
                    (b, y0), e - b, y1 - y0 + 0.9, color=color, alpha=alpha, label=label
                )
                ax.add_artist(rect)


def plot_mstates(mstates_df, ax=None, title=None, palette=None, reverse=True):
    # Parameter handling
    if palette is None:
        # Colorblind palette
        palette = ["#000000", "#56ae6c", "#ba495b", "#000000", "#8960b3"]

    stack_order = [
        "nb_sleeping",
        "nb_switching_on",
        "nb_switching_off",
        "nb_idle",
        "nb_computing",
    ]

    alphas = [0.6, 1, 1, 0, 0.3]

    assert len(palette) == len(stack_order), "Palette should be of size {}".format(
        len(stack_order)
    )

    # Get current axe to plot
    if ax is None:
        ax = plt.gca()

    # Should the display order be reversed?
    if reverse:
        palette = palette[::-1]
        stack_order = stack_order[::-1]
        alphas = alphas[::-1]

    # Computing temporary date to compute the stacked area
    y = np.row_stack(tuple([mstates_df[x] for x in stack_order]))
    y = np.cumsum(y, axis=0)

    # Plotting
    first_i = 0
    ax.fill_between(
        mstates_df["time"],
        0,
        y[first_i, :],
        facecolor=palette[first_i],
        alpha=alphas[first_i],
        step="post",
        label=stack_order[first_i],
    )

    for index, _ in enumerate(stack_order[1:]):
        ax.fill_between(
            mstates_df["time"],
            y[index, :],
            y[index + 1, :],
            facecolor=palette[index + 1],
            alpha=alphas[index + 1],
            step="post",
            label=stack_order[index + 1],
        )

    if title is not None:
        ax.set_title(title)


def plot_gantt_pstates(
    jobset,
    pstates,
    ax,
    title,
    labels=True,
    off_pstates=None,
    son_pstates=None,
    soff_pstates=None,
):

    if off_pstates is None:
        off_pstates = set()
    if son_pstates is None:
        son_pstates = set()
    if soff_pstates is None:
        soff_pstates = set()
    plot_gantt(jobset, ax, title, labels, palette=["#8960b3"], alpha=0.3)

    fpb = pstates.pseudo_jobs.loc[pstates.pseudo_jobs["end"] < float("inf")]

    ax.set_xlim(
        min(jobset.df.submission_time.min(), fpb.begin.min()),
        max(jobset.df.finish_time.max(), fpb.end.max()),
    )
    ax.set_ylim(
        min(jobset.res_bounds[0], pstates.res_bounds[0]),
        max(jobset.res_bounds[1], pstates.res_bounds[1]),
    )
    ax.grid(True)
    ax.set_title(title)

    plot_pstates(
        pstates,
        ax.get_xlim()[1],
        ax,
        off_pstates=off_pstates,
        son_pstates=son_pstates,
        soff_pstates=soff_pstates,
    )


def plot_processor_load(jobset, ax=None, title="Load", labels=True):
    """
    Display the impact of each job on the load of each processor.

    need: execution_time, jobID, allocated_resources
    """

    # Get current axe to plot
    if ax is None:
        ax = plt.gca()

    def _draw_rect(ax, base, width, height, color, label):
        rect = mpatch.Rectangle(base, width, height, alpha=0.2, color=color)
        if label:
            annotate(ax, rect, label)
        ax.add_artist(rect)

    RGB_tuples = core.generate_palette(16)
    load = {p: 0.0 for p in range(jobset.res_bounds[0], jobset.res_bounds[1] + 1)}

    for row in jobset.df.itertuples():
        color = RGB_tuples[row.Index % len(RGB_tuples)]
        duration = row.execution_time
        label = row.jobID if labels else None

        baseproc = next(iter(row.allocated_resources))
        base = (baseproc, load[baseproc])
        width = 0  # width is incremented in the first loop iteration
        for proc in row.allocated_resources:
            if base[0] + width != proc or load[proc] != base[1]:
                # we cannot merge across processors: draw the current
                # rectangle, and start anew
                _draw_rect(ax, base, width, duration, color, label)
                base = (proc, load[proc])
                width = 1
            else:
                # we can merge across processors: extend width, and continue
                width += 1
            load[proc] += duration

        # draw last pending rectangle if necessary
        if width > 0:
            _draw_rect(ax, base, width, duration, color, label)

    ax.set_xlim(jobset.res_bounds)
    ax.set_ylim(0, 1.02 * max(load.values()))
    ax.grid(True)
    ax.set_title(title)
    ax.set_xlabel("proc. id")
    ax.set_ylabel("load / s")


def plot_series(series_type, jobsets, ax=None, time_scale=False):
    """
    Plot one or several time series about provided jobsets on the given ax
    series_type can be any value present in available_series.
    """
    # Get current axe to plot
    if ax is None:
        ax = plt.gca()

    if series_type not in available_series:
        raise AttributeError(
            "The gieven attribute should be one of the folowing:"
            "{}".format(available_series)
        )

    if series_type == "waiting_time":
        series = {}
        for jobset_name in jobsets.keys():
            jobset = jobsets[jobset_name]
            #  create a serie
            series[jobset_name] = metrics.cumulative_waiting_time(jobset.df)
            if time_scale:
                series[jobset_name].index = pd.to_datetime(
                    jobset.df["submission_time"] + jobset.df["waiting_time"], unit="s"
                )
        # plot series
        for serie_name, serie in series.items():
            serie.plot(ax=ax, label=serie_name, drawstyle="steps")
    else:
        raise RuntimeError('The serie "{}" is not implemeted yet')

    # Manage legend
    ax.legend()
    ax.set_title(series_type)
    ax.grid(True)


def plot_gantt_general_shape(
    jobset_list, ax=None, alpha=0.3, title="Gantt general shape"
):
    """
    Draw a general gantt shape of multiple jobsets on one plot for comparison
    """
    # Get current axe to plot
    if ax is None:
        ax = plt.gca()

    color_index = 0
    RGB_tuples = core.generate_palette(len(jobset_list))
    legend_rect = []
    legend_label = []
    xmin = None
    xmax = None
    for jobset_name, jobset in jobset_list.items():
        # generate color
        color = RGB_tuples[color_index % len(RGB_tuples)]
        color_index += 1

        # generate legend
        legend_rect.append(mpatch.Rectangle((0, 1), 12, 10, alpha=alpha, color=color))
        legend_label.append(jobset_name)

        def plot_job(job):
            duration = job["execution_time"]
            for itv in job["allocated_resources"].intervals():
                (y0, y1) = itv
                rect = mpatch.Rectangle(
                    (job["starting_time"], y0),
                    duration,
                    y1 - y0 + 0.9,
                    alpha=alpha,
                    color=color,
                )
                ax.add_artist(rect)

        # apply for all jobs
        jobset.df.apply(plot_job, axis=1)

        # compute graphical boundaries
        if not xmin or jobset.df.submission_time.min() < xmin:
            xmin = jobset.df.submission_time.min()
        if not xmax or jobset.df.finish_time.max() < xmax:
            xmax = jobset.df.finish_time.max()

    # do include legend
    ax.legend(
        legend_rect,
        legend_label,
        loc="center",
        bbox_to_anchor=(0.5, 1.06),
        fancybox=True,
        shadow=True,
        ncol=5,
    )
    ax.set_xlim((xmin, xmax))
    # use last jobset of the previous loop to set the resource bounds assuming
    # that all the gantt have the same number of resources
    ax.set_ylim(jobset.res_bounds[0] - 1, jobset.res_bounds[1] + 2)
    ax.grid(True)
    ax.set_title(title)
    ax.set_ylabel("Machines")


def plot_job_details(
    dataframe, size, ax=None, title="Job details", time_scale=False, time_offset=0
):
    # TODO manage also the Jobset case
    # Get current axe to plot
    if ax is None:
        ax = plt.gca()

    # Avoid side effect
    df = pd.DataFrame.copy(dataframe)
    df = df.sort_values(by="jobID")

    df["submission_time"] = pd.to_datetime(df["submission_time"], unit='s') + pd.to_timedelta(time_offset, unit='s')
    df["starting_time"] = pd.to_datetime(df["submission_time"]) + pd.to_timedelta(df["waiting_time"], unit='s')
    df["finish_time"] = pd.to_datetime(df["starting_time"]) + pd.to_timedelta(df["execution_time"], unit='s')

    threshold = size * 1.05  # To separate the 3 "zones"

    to_plot = [
        ("submission_time", "blue", ".", 0),
        ("starting_time", "green", ">", threshold),
        ("finish_time", "red", "|", threshold * 2),
    ]

    lines = [
        ["submission_time", "starting_time", "blue", 0, threshold],
        ["starting_time", "finish_time", "green", threshold, threshold * 2],
    ]

    if time_scale:
        # interpret columns with time aware semantics
        df["submission_time"] = pd.to_datetime(df["submission_time"], unit="s")
        df["starting_time"] = pd.to_datetime(df["starting_time"], unit="s")
        df["finish_time"] = pd.to_datetime(df["finish_time"], unit="s")
        # convert columns to use them with matplotlib
        df["submission_time"] = df["submission_time"].map(matplotlib.dates.date2num)
        df["starting_time"] = df["starting_time"].map(matplotlib.dates.date2num)
        df["finish_time"] = df["finish_time"].map(matplotlib.dates.date2num)

    # select the axe
    plt.sca(ax)

    # plot lines
    # add jitter
    jitter = size / 20
    random.seed(a=0)
    new_proc_alloc = df["proc_alloc"].apply(
        lambda x: x + random.uniform(-jitter, jitter)
    )
    for begin, end, color, treshold_begin, treshold_end in lines:
        for i, item in df.iterrows():
            x_begin = item[begin]
            x_end = item[end]
            plt.plot(
                [x_begin, x_end],
                [new_proc_alloc[i] + treshold_begin, new_proc_alloc[i] + treshold_end],
                color=color,
                linestyle="-",
                linewidth=1,
                alpha=0.2,
            )

    # plot one point per serie
    for serie, color, marker, treshold in to_plot:
        x = df[serie]
        y = new_proc_alloc + treshold
        plt.scatter(x, y, c=color, marker=marker, s=60, label=serie, alpha=0.5)

    ax.grid(True)
    ax.legend()
    ax.set_title(title)
    ax.set_ylabel("Job size")
    if time_scale:
        ax.xaxis.set_major_formatter(
            matplotlib.dates.DateFormatter("%Y-%m-%d\n%H:%M:%S")
        )


def plot_series_comparison(series, ax=None, title="Series comparison"):
    """Plot and compare two serie in post step"""
    assert len(series) == 2
    # Get current axe to plot
    if ax is None:
        ax = plt.gca()

    first_serie_name = list(series.keys())[0]
    first_serie = list(series.values())[0]
    first_serie.plot(drawstyle="steps-post", ax=ax, label=first_serie_name)

    second_serie_name = list(series.keys())[1]
    second_serie = list(series.values())[1]
    second_serie.plot(drawstyle="steps-post", ax=ax, label=second_serie_name)

    df = pd.DataFrame(series, index=first_serie.index).fillna(method="ffill")
    y1 = df[first_serie_name]
    y2 = df[second_serie_name]
    ax.fill_between(
        df.index,
        y1,
        y2,
        where=y2 < y1,
        facecolor="red",
        step="post",
        alpha=0.5,
        label=first_serie_name + ">" + second_serie_name,
    )
    ax.fill_between(
        df.index,
        y1,
        y2,
        where=y2 > y1,
        facecolor="green",
        step="post",
        alpha=0.5,
        label=first_serie_name + "<" + second_serie_name,
    )
    ax.grid(True)
    ax.set_title(title)


def plot_fragmentation(frag, ax=None, label="Fragmentation"):
    """
    Plot fragmentation raw data, distribution and ecdf in 3 subplots
    given in the ax list
    fragmentation can be optain using fragmentation method
    """
    # Get current axe to plot
    if ax is None:
        ax = plt.subplots(nrows=3)

    assert len(ax) == 3

    # direct plot
    frag.plot(ax=ax[0], label=label)
    ax[0].set_title("Fragmentation over resources")

    # plot distribution
    sns.distplot(frag, ax=ax[1], label=label, kde=False, rug=True)
    ax[1].set_title("Fragmentation distribution")

    # plot ecdf
    from statsmodels.distributions.empirical_distribution import ECDF

    ecdf = ECDF(frag)
    ax[2].step(ecdf.x, ecdf.y, label=label)
    ax[2].set_title("Fragmentation ecdf")


def plot_load(
    load,
    nb_resources=None,
    ax=None,
    normalize=False,
    time_scale=False,
    legend_label="Load",
    UnixStartTime=0,
    TimeZoneString="UTC",
    windowStartTime=False,
    windowFinishTime=False,
    power=None,
    normalize_power=False,
):
    """
    Plots the number of used resources against time
    :normalize: if True normalize by the number of resources
    `nb_resources`
    """
    mean = metrics.load_mean(load)
    u = load.copy()
    if power is not None:
        # power_mean = metrics.load_mean(power)
        p = power.copy()

    if time_scale:
        # make the time index a column
        u = u.reset_index()
        # convert timestamp to datetime
        u.index = pd.to_datetime(u["time"] + UnixStartTime, unit="s")
        u.index.tz_localize("UTC").tz_convert(TimeZoneString)

    if normalize and nb_resources is None:
        nb_resources = u.load.max()

    if normalize:
        u.load = u.load / nb_resources
        mean = mean / nb_resources

    if normalize_power:
        max_power = p.load.max()
        p.load = p.load / max_power
        p.load = p.load * u.load.max()
        # power_mean = power_mean / max_power

    # get an axe if not provided
    if ax is None:
        ax = plt.gca()

    # leave room to have better view
    ax.margins(x=0.1, y=0.1)

    # plot load
    u.load.plot(drawstyle="steps-post", ax=ax, label=legend_label)

    if power is not None:
        par = ax.twinx()
        p.load.plot(drawstyle="steps-post", ax=par, label="consumedEnergy", color="purple")


    # plot a line for max available area
    if nb_resources and not normalize:
        ax.plot(
            [u.index[0], u.index[-1]],
            [nb_resources, nb_resources],
            linestyle="-",
            linewidth=2,
            label="Maximum resources ({})".format(nb_resources),
        )

    # plot a line for mean utilisation
    ax.plot(
        [u.index[0], u.index[-1]],
        [mean, mean],
        linestyle="--",
        linewidth=1,
        label="Mean {0} ({1:.2f})".format(legend_label, mean),
    )

    # if power is not None:
    #     ax.plot(
    #         [p.index[0], p.index[-1]],
    #         [power_mean, power_mean],
    #         linestyle="--",
    #         linewidth=1,
    #         label="Mean {0} ({1:.2f})".format(legend_label, power_mean),
    #     )

    sns.rugplot(u.load[u.load == 0].index, ax=ax, color="r")
    ax.scatter(
        [],
        [],
        marker="|",
        linewidth=1,
        s=200,
        label="Reset event ({} == 0)".format(legend_label),
        color="r",
    )
    # FIXME: Add legend when this bug is fixed
    # https://github.com/mwaskom/seaborn/issues/1071

    # ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    if windowStartTime and windowFinishTime:
        ax.set_xlim(windowStartTime, windowFinishTime)
    ax.grid(True)

    if power is not None:
        par.legend(loc="lower right")
        par.set_ylabel("consumedEnergy")
    ax.set_ylabel("Machines")
    ax.set_xlabel("Time")
    ax.legend(labelcolor="linecolor")
    plt.tight_layout()


def plot_binned_load(
    loadSmall,
    loadLong,
    loadLarge,
    nb_resources=None,
    nb_resourcesSmall=None,
    nb_resourcesLong=None,
    nb_resourcesLarge=None,
    ax=None,
    normalize=False,
    time_scale=False,
    legend_label="Load",
    UnixStartTime=0,
    TimeZoneString="UTC",
    divisor=None,
    loadOverall=None,
    reservationStartTime=None,
    reservationFinishTime=None,
    xAxisTermination=None,
):
    """
    Plots the number of used resources against time
    :normalize: if True normalize by the number of resources
    `nb_resources`
    """
    meanSmall = metrics.load_mean(loadSmall)
    # meanSmallRaw = metrics.load_mean(loadSmall)
    u = loadSmall.copy()
    # uu = loadSmall.copy()
    meanLong = metrics.load_mean(loadLong)
    # meanLongRaw = metrics.load_mean(loadLong)
    l = loadLong.copy()
    # ll = loadLong.copy()
    meanLarge = metrics.load_mean(loadLarge)
    # meanLargeRaw = metrics.load_mean(loadLarge)
    x = loadLarge.copy()
    # xx = loadLarge.copy()
    if divisor != None:
        meanOverall = metrics.load_mean(loadOverall)
        # meanOverallRaw = metrics.load_mean(loadOverall)
        o = loadOverall.copy()
        # oo = loadOverall.copy()

    if time_scale:
        # make the time index a column
        u = u.reset_index()
        l = l.reset_index()
        x = x.reset_index()
        # uu = uu.reset_index()
        # ll = ll.reset_index()
        # xx = xx.reset_index()

        # convert timestamp to datetime
        u.index = pd.to_datetime(u["time"] + UnixStartTime, unit="s")
        l.index = pd.to_datetime(l["time"] + UnixStartTime, unit="s")
        x.index = pd.to_datetime(x["time"] + UnixStartTime, unit="s")
        # uu.index = pd.to_datetime(uu["time"] + UnixStartTime, unit="s")
        # ll.index = pd.to_datetime(ll["time"] + UnixStartTime, unit="s")
        # xx.index = pd.to_datetime(xx["time"] + UnixStartTime, unit="s")

        u.index.tz_localize("UTC").tz_convert(TimeZoneString)
        l.index.tz_localize("UTC").tz_convert(TimeZoneString)
        x.index.tz_localize("UTC").tz_convert(TimeZoneString)
        # uu.index.tz_localize("UTC").tz_convert(TimeZoneString)
        # ll.index.tz_localize("UTC").tz_convert(TimeZoneString)
        # xx.index.tz_localize("UTC").tz_convert(TimeZoneString)

    if normalize and nb_resources is None:
        nb_resourcesSmall = u.load.max()
        nb_resourcesLong = l.load.max()
        nb_resourcesLarge = x.load.max()
        # FIXME this isnt ready for the double line set

    if normalize:
        u.load = u.load / nb_resourcesSmall
        l.load = l.load / nb_resourcesLong
        x.load = x.load / nb_resourcesLarge

        meanSmall = meanSmall / nb_resourcesSmall
        meanLong = meanLong / nb_resourcesLong
        meanLarge = meanLarge / nb_resourcesLarge

    if divisor != None:
        u.load = u.load / divisor
        l.load = l.load / divisor
        x.load = x.load / divisor
        o.load = o.load / divisor

        meanSmall = meanSmall / divisor
        meanLong = meanLong / divisor
        meanLarge = meanLarge / divisor
        meanOverall = meanOverall / divisor

    # get an axe if not provided
    if ax is None:
        ax = plt.gca()

    # leave room to have better view
    ax.margins(x=0.1, y=0.1)

    # plot load
    u.load.plot(
        drawstyle="steps-post",
        ax=ax,
        linewidth=2,
        label="Small job " + legend_label,
    )
    l.load.plot(
        drawstyle="steps-post", ax=ax, linewidth=2, label="Long job " + legend_label
    )
    x.load.plot(
        drawstyle="steps-post",
        ax=ax,
        linewidth=2,
        label="Large job " + legend_label,
    )
    if divisor != None:
        o.load.plot(
            drawstyle="steps-post", ax=ax, linewidth=2, label="Overall " + legend_label
        )
        # uu.load.plot(
        #     drawstyle="steps-post",
        #     ax=ax,
        #     linewidth=2,
        #     label="Small jobs raw " + legend_label,
        # )
        # ll.load.plot(
        #     drawstyle="steps-post",
        #     ax=ax,
        #     linewidth=2,
        #     label="Long jobs raw " + legend_label,
        # )
        # xx.load.plot(
        #     drawstyle="steps-post",
        #     ax=ax,
        #     linewidth=2,
        #     label="Large jobs raw " + legend_label,
        # )
        # oo.load.plot(
        #     drawstyle="steps-post",
        #     ax=ax,
        #     linewidth=2,
        #     label="Overall raw " + legend_label,
        # )
    # plot a line for max available area
    if nb_resourcesSmall and nb_resourcesLong and nb_resourcesLarge and not normalize:
        ax.plot(
            [u.index[0], u.index[-1]],
            [nb_resourcesSmall, nb_resourcesSmall],
            linestyle="-",
            linewidth=4,
            label="Maximum resources for Small Jobs ({})".format(nb_resourcesSmall),
        )
        ax.plot(
            [l.index[0], l.index[-1]],
            [nb_resourcesLong, nb_resourcesLong],
            linestyle="-",
            linewidth=4,
            label="Maximum resources for Long Jobs ({})".format(nb_resourcesLong),
        )
        ax.plot(
            [x.index[0], x.index[-1]],
            [nb_resourcesLarge, nb_resourcesLarge],
            linestyle="-",
            linewidth=4,
            label="Maximum resources for Large Jobs ({})".format(nb_resourcesLarge),
        )

    # plot a line for mean utilisation
    ax.plot(
        [u.index[0], u.index[-1]],
        [meanSmall, meanSmall],
        linestyle="--",
        linewidth=1,
        label="Mean {0} for Small Jobs ({1:.2f})".format(legend_label, meanSmall),
    )
    ax.plot(
        [l.index[0], l.index[-1]],
        [meanLong, meanLong],
        linestyle="--",
        linewidth=1,
        label="Mean {0} for Long Jobs ({1:.2f})".format(legend_label, meanLong),
    )
    ax.plot(
        [x.index[0], x.index[-1]],
        [meanLarge, meanLarge],
        linestyle="--",
        linewidth=1,
        label="Mean {0} for Large Jobs ({1:.2f})".format(legend_label, meanLarge),
    )
    if divisor != None:
        ax.plot(
            [o.index[0], o.index[-1]],
            [meanOverall, meanOverall],
            linestyle="--",
            linewidth=1,
            label="Mean {0} for Overall Jobs ({1:.2f})".format(
                legend_label, meanOverall
            ),
        )
        # ax.plot(
        #     [uu.index[0], uu.index[-1]],
        #     [meanSmallRaw, meanSmallRaw],
        #     linestyle="--",
        #     linewidth=1,
        #     label="Mean {0} for Raw Small Jobs ({1:.2f})".format(
        #         legend_label, meanSmallRaw
        #     ),
        # )
        # ax.plot(
        #     [ll.index[0], ll.index[-1]],
        #     [meanLongRaw, meanLongRaw],
        #     linestyle="--",
        #     linewidth=1,
        #     label="Mean {0} for Raw Long Jobs ({1:.2f})".format(
        #         legend_label, meanLongRaw
        #     ),
        # )
        # ax.plot(
        #     [xx.index[0], xx.index[-1]],
        #     [meanLargeRaw, meanLargeRaw],
        #     linestyle="--",
        #     linewidth=1,
        #     label="Mean {0} for Raw Large Jobs ({1:.2f})".format(
        #         legend_label, meanLargeRaw
        #     ),
        # )
        # ax.plot(
        #     [oo.index[0], oo.index[-1]],
        #     [meanOverallRaw, meanOverallRaw],
        #     linestyle="--",
        #     linewidth=1,
        #     label="Mean {0} for Raw Overall Jobs ({1:.2f})".format(
        #         legend_label, meanOverallRaw
        #     ),
        # )
    # This handles drawing the reset markers
    sns.rugplot(u.load[u.load == 0].index, ax=ax, color="r")
    sns.rugplot(l.load[l.load == 0].index, ax=ax, color="r")
    sns.rugplot(x.load[x.load == 0].index, ax=ax, color="r")

    # Draw markers for the reservation's start and stop points
    if divisor != None:
        d = {"time": [reservationStartTime, reservationFinishTime], "yaxis": [0, 0]}
        df = pd.DataFrame(data=d)
        sns.rugplot(d, ax=ax, color="y")

    ax.scatter(
        [],
        [],
        marker="|",
        linewidth=1,
        s=200,
        label="Reset event ({} == 0)".format(legend_label),
        color="r",
    )
    # FIXME: Add legend when this bug is fixed
    # https://github.com/mwaskom/seaborn/issues/1071

    # ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    if divisor != None:
        ax.set(
            xlim=(0, xAxisTermination),
            ylim=(-10, (loadOverall.load.max() / divisor) + 10),
        )
    else:
        # FIXME Unhardcode this
        ax.set(
            ylim=(-10, (1490) + 10),
        )

    # else:
    #     ax.set(ylim=(-10, xx.load.max() + 10))
    ax.grid(True)
    ax.legend()
    ax.set_title("Cluster Utilization by Job Type")
    ax.set_ylabel("Machines")


def plot_free_resources(
    utilisation,
    nb_resources,
    normalize=False,
    time_scale=False,
    UnixStartTime=0,
    TimeZoneString="UTC",
):
    """
    Plots the number of free resources against time
    :normalize: if True normalize by the number of resources `nb_resources`
    """
    free = nb_resources - utilisation

    if normalize:
        free = free / nb_resources

    if time_scale:
        free.index = pd.to_datetime(free["time"] + UnixStartTime, unit="s", utc=True)
        free.index.tz_localize("UTC").tz_convert(TimeZoneString)

    free.plot()
    # plot a line for the number of procs
    plt.plot(
        [free.index[0], free.index[-1]],
        [nb_resources, nb_resources],
        linestyle="-",
        linewidth=1,
        label="Maximum resources ({})".format(nb_resources),
    )
