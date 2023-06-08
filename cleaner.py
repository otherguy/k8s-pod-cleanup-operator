# !/usr/bin/env python3
# -*- coding:utf-8 -*-
#
import pykube
import time
import argparse
from decouple import config
from tempora import parse_timedelta
from random import sample
from requests.exceptions import RequestException
import datetime
import json
import os
from typing import Union
import signal
import sys


def signal_handler(sig, frame):
    """Signal handler callback"""
    print("SIGINT received. Exiting.")
    sys.exit(0)


def parse_time(s: str):
    """[summary]

    Args:
        s (str): The timestamp to parse.

    Returns:
        float: POSIX timestamp as float
    """
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def get_kubernetes_interface():
    """Retrieves a pykube.HTTPClient interface either from a service account or, for
       local development, from the user's ~/.kube/config.

    Returns:
        pykube.HTTPClient: A pykube.HTTPClient interface
    """
    try:
        config = pykube.KubeConfig.from_service_account()
        print("Using Kubernetes service account for authentication")
    except FileNotFoundError:
        config = pykube.KubeConfig.from_file(os.path.expanduser("~/.kube/config"))
        print("Using local ~/.kube/config for authentication")

    return pykube.HTTPClient(config)


def container_finish_time(status):
    terminated_state = status.get("state", {}).get("terminated") or status.get("lastState")
    if terminated_state:
        finish_time = terminated_state.get("finishedAt")
        if finish_time:
            return parse_time(finish_time).timestamp()


def entity_termination_time(entity: Union[pykube.objects.Pod, pykube.objects.Job]):
    """Determines the termination time of an enity.

    Args:
        eentity (pykube.objects.Pod, pykube.objects.Job): The entity to inspect.

    Returns:
        None|int: None if the termination time cannot be determined, a time offset in seconds otherwise
    """
    pod_status = entity.obj.get("status")
    container_statuses = pod_status.get("initContainerStatuses", []) + pod_status.get("containerStatuses", [])
    finish_times = list(filter(None, (container_finish_time(status) for status in container_statuses)))
    if not finish_times:
        return None
    return max(finish_times)


def is_entity_expired(entity: Union[pykube.objects.Pod, pykube.objects.Job], max_age_seconds: int):
    """Compares the age since termination to max_age_seconds and determines whether
       the entity is expired.

    Args:
        entity (pykube.objects.Pod, pykube.objects.Job): The entity to inspect.
        max_age_seconds (int): Maximum allowed age of the entity.

    Returns:
        None|int: None if the entity is not expired, otherwise the age in seconds.
    """

    # If we cannot determine the finish time, use start time instead
    finish_time = (entity_termination_time(entity) or parse_time(entity.obj.get("metadata").get("creationTimestamp")).timestamp())
    seconds_since_completion = time.time() - finish_time

    if seconds_since_completion > max_age_seconds:
        return int(seconds_since_completion)

    # Can't return False due to False == 0 in comparison
    return None


def delete_entity(entity: Union[pykube.objects.Pod, pykube.objects.Job], max_age_seconds: int, dry_run: bool = False):
    """Delete an entity if it's older than a given max age and dry run is disabled.

    Args:
        entity (pykube.objects.Pod, pykube.objects.Job): The entity to delete.
        max_age_seconds (int): The maximum allowed age of the entity in seconds.
        dry_run (bool, optional): Whether this is a dry run. Defaults to False.

    Returns:
        bool: Whether the entity was deleted
    """

    # Verify if the entity is expired and can be deleted
    entity_age = is_entity_expired(entity, max_age_seconds)
    if entity_age == None:
        return False

    # Prepare message if this is a dry run
    dry_run_message = "[DRY RUN] " if dry_run else ""

    print("{}Deleting {} {} in namespace {} because of {} ({}) status and age {}s.".format(dry_run_message, entity.kind, entity.name, entity.namespace, entity.obj["status"].get("phase"), entity.obj["status"].get("reason"), entity_age))

    if dry_run == False:
        return entity.delete()

    return False


def parse_deletion_status(status: str):
    """Parses a status passed as a CLI argument and returns a tuple
       with the phase and reason.

       E.g. parse_deletion_status("Failed:Shutdown") will return ("Failed", "Shutdown")

    Args:
        status (str): a status passed as a CLI argument

    Returns:
        (str, str): Tuple containing the phase and reason
    """
    bits = status.split(":")
    assert len(bits) <= 2, "Too many ':' in status selector!"

    phase = bits[0]
    reason = None

    if len(bits) == 2:
        reason = bits[1]

    return phase, reason


def strfdelta_round(tdelta, round_period="second"):
    """Returns a human readable string representation of a timedelta object.

    Args:
        tdelta (datetime.timedelta): The timedelta object to convert
        round_period (str, optional): The rounding period. Defaults to "second"

    Returns:
        str: A human readable string representation of the timedelta object
    """
    period_names = ("day", "hour", "minute", "second", "millisecond")
    if round_period not in period_names:
        raise ValueError(f'round_period "{round_period}" invalid, should be one of {",".join(period_names)}')
    period_seconds = (86400, 3600, 60, 1, 1 / pow(10, 3))
    period_desc = ("days", "hrs", "min", "sec", "msec")
    round_i = period_names.index(round_period)

    s = ""
    remainder = tdelta.total_seconds()
    for i in range(len(period_names)):
        q, remainder = divmod(remainder, period_seconds[i])
        if int(q) > 0:
            if not len(s) == 0:
                s += " "
            s += f"{q:.0f}{period_desc[i]}"
        if i == round_i:
            break
        if i == round_i + 1:
            s += f"{remainder}{period_desc[round_i]}"
            break

    return s


def main():
    """
    K8s Pod Cleanup Operator

    Parameters:

    -n (--namespace):      Limits the scope to a certain namespace
    -g (--graceperiod):          Time in seconds [default: 300] to wait before deleting the Pod or Job
    -l (--label-selector): Delete only Jobs and Pods that meet the label selector
    --dry-run:             Only print info, do not actually delete pods

    status [status ...]:   Statuses of Pods and Jobs that should be considered for deletion.
    """

    # Gracefully handle SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)

    # Parse command line arguments
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-n",
        "--namespace",
        type=str,
        default=pykube.all,
        help="Limit the scope to a single namespace [default: all namespaces]",
    )
    parser.add_argument(
        "-u",
        "--user",
        action="store_true",
        default=False,
        help="Limit the scope to only user namespaces and exclude kube-system objects",
    )
    parser.add_argument(
        "-g",
        "--graceperiod",
        type=int,
        default=300,
        help="Time in seconds [default: 300] to wait before deleting the Pod or Job",
    )
    parser.add_argument(
        "-l",
        "--label-selector",
        type=str,
        default="{}",
        help="Delete only Jobs and Pods that meet the label selector",
    )
    parser.add_argument(
        "--skip-with-owner",
        action="store_true",
        default=False,
        help="Skip deletion of pods which currently have an active owner reference",
    )
    parser.add_argument(
        "--lifetime-annotation",
        type=str,
        default="pod.kubernetes.io/lifetime",
        help="Pod annotation to use for the maximum age of the pod",
    )
    parser.add_argument(
        "--lifetime-max-kills",
        type=int,
        default=1,
        help="Maximum number of pods to kill in one run due to lifetime expires",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Be more quiet and only print output when actually deleting pods",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Time in seconds [default: 60] to wait between two runs",
    )
    parser.add_argument(
        "--error-limit",
        type=int,
        default=5,
        help="How many consecutive errors [default: 5] are allowed before exiting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print only, do not delete anything",
    )
    parser.add_argument(
        "status",
        nargs="+",
        help="Statuses of Pods and Jobs that should be considered for deletion",
    )

    args = parser.parse_args()

    # Fetch Version, VCS ref and build date from env (see: Dockerfile)
    app_version = config("VERSION", default="0.x")
    app_vcs_ref = config("VCS_REF", default="main")
    app_build_date = config("BUILD_DATE", default=datetime.datetime.now(datetime.timezone.utc).isoformat())
    print("Pod Cleanup Operator. Version: {}, Commit: {}, Build Date: {}".format(app_version, app_vcs_ref, app_build_date))

    # Get a Kubernetes API instance
    kubectl = get_kubernetes_interface()

    # Start error counter
    errorcount = 0

    # Main application loop
    while True:
        pod_deletion_counter = 0
        job_deletion_counter = 0

        # Get all pods ...
        # - in the specified namespace
        # - that are not in 'Running' state and
        # - that match the --label-selector argument
        try:

            # Select pods to delete based on their phase and user specified selectors
            for pod in pykube.Pod.objects(kubectl).filter(namespace=args.namespace, field_selector="status.phase!=Running", selector=json.loads(args.label_selector)):

                # Retrieve pod status object containing reason etc.
                pod_status = pod.obj["status"]

                # Preempting pods don't have any container information, delete immediately
                if pod_status.get("reason") == "Preempting":
                    delete_entity(pod, 0, args.dry_run)
                    pod_deletion_counter += 1

                # Loop over all requested deletion statuses...
                for deletion_status in args.status:
                    phase, reason = parse_deletion_status(deletion_status)

                    if pod_status.get("phase") == phase:
                        if reason == None or pod_status.get("reason") == reason:
                            if pod.namespace == "kube-system" and args.user == True:
                                if not args.quiet:
                                    print("Skipping system pod {} in {} namespace".format(pod.name, pod.namespace))
                            else:
                                if args.skip_with_owner and pod.metadata.get("ownerReferences"):
                                    if not args.quiet:
                                        print("Skipping pod with owner reference {} in {} namespace".format(pod.name, pod.namespace))
                                    continue
                                delete_entity(pod, args.graceperiod, args.dry_run)
                                pod_deletion_counter += 1

            # Sleep 15 seconds before running the next iteration.
            if not args.quiet or (pod_deletion_counter > 0 or job_deletion_counter > 0):
                print("Deleted {} pods and {} jobs.".format(pod_deletion_counter, job_deletion_counter))

            # Select pods to be killed based on their lifetime.
            expired_pods = []
            for pod in pykube.Pod.objects(kubectl).filter(namespace=args.namespace, field_selector="status.phase==Running"):

                # Retrieve pod status object containing reason etc.
                if args.lifetime_annotation in pod.annotations:
                    pod_annotated_lifetime = pod.annotations.get(args.lifetime_annotation, "")
                    pod_creation_timestamp = parse_time(pod.metadata.get("creationTimestamp"))

                    try:
                        pod_annotated_lifetime_timedelta = parse_timedelta(pod_annotated_lifetime)
                        if (datetime.datetime.now().astimezone() - pod_creation_timestamp) > pod_annotated_lifetime_timedelta:
                            if not args.quiet:
                                print("Pod {} in {} namespace has '{}' annotation of {} and will be considered for termination (actual age {})".format(pod.name, pod.namespace, args.lifetime_annotation, pod_annotated_lifetime, strfdelta_round(datetime.datetime.now().astimezone() - pod_creation_timestamp), pod_annotated_lifetime_timedelta))
                            if args.skip_with_owner and pod.metadata.get("ownerReferences"):
                                if not args.quiet:
                                    print("Skipping pod with owner reference {} in {} namespace".format(pod.name, pod.namespace))
                                continue

                            expired_pods.append(pod)

                    except (TypeError, ValueError) as err:
                        print("Pod {} in {} namespace has '{}' annotation with value '{}' but it cannot be parsed: {}".format(pod.name, pod.namespace, args.lifetime_annotation, pod_annotated_lifetime, err), file=sys.stderr)

            if len(expired_pods) > 0:
                if not args.quiet:
                    print("Found {} expired pods, killing a maximum of {} during this run.".format(len(expired_pods), args.lifetime_max_kills))
                for pod in sample(expired_pods, min(len(expired_pods), args.lifetime_max_kills)):
                    dry_run_message = "[DRY RUN] " if args.dry_run else ""
                    pod_annotated_lifetime = pod.annotations.get(args.lifetime_annotation, "")
                    pod_creation_timestamp = parse_time(pod.metadata.get("creationTimestamp"))
                    print("{}Deleting pod {} in namespace {} because its age of {} exceeds the maximum age of {}.".format(dry_run_message, pod.name, pod.namespace, strfdelta_round(datetime.datetime.now().astimezone() - pod_creation_timestamp), pod_annotated_lifetime))

                    if args.dry_run == False:
                        pod.delete()

            # Sleep for the given interval
            time.sleep(args.interval)

            # Reset error counter
            errorcount = 0

        except pykube.exceptions.KubernetesError as err:
            print("KubernetesError: {0}".format(err), file=sys.stderr)
            time.sleep(args.interval*1.5)
            errorcount += 1
        except RequestException as err:
            print("RequestException: {0}".format(str(err)), file=sys.stderr)
            time.sleep(args.interval*1.5)
            errorcount += 1
        finally:
            if errorcount >= args.error_limit:
                print("Too many errors ({}) when communicating with the control plane, stopping now.".format(args.error_limit), file=sys.stderr)
                sys.exit(1)


###############################################################################

if __name__ == "__main__":
    main()
