# ☸️ K8s Pod Cleanup Operator

A Kubernetes Operator to clean up expired pods in any desired non-running state.

## 🛠 What does it do?

This lightweight Kubernetes Operator will clean up expired pods in any desired non-running state.

For example, pods with `Evicted` or `Terminated` reason, or even all `Failed` or `Succeeded` pods regardless
of their termination reason, can be cleaned up.

Additionally, this operator can be used to clean up pods that are running for a specified amount of time.

To give a pod a certain lifetime, add the `pod.kubernetes.io/lifetime` annotation to the pod. The value of this annotation
needs to be a valid duration in a format [understandable to `parse_timedelta`](https://tempora.readthedocs.io/en/latest/#tempora.parse_timedelta).

Example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example
spec:
  template:
    metadata:
      annotations:
        pod.kubernetes.io/lifetime: "12 hours"
```

## 🚀 Usage and Deployment

- First, you need a _Kubernetes Service Account_ with the permission to look and, if necessary, delete Pods and Jobs.
- Then, adapt the [`deployment.yaml`](k8s/deployment.yaml) to suit your needs. This involves picking the correct image
  tag and modifying the `args` to suit your requirements.
- Lastly, apply the Deployment to your cluster.

_**Note:** You cannot create a Role that defines permissions unless you already have the permissions defined in the Role. If you
have been granted the [cluster-admin](https://cloud.google.com/iam/docs/understanding-roles#kubernetes-engine-roles) IAM role,
this is sufficient._

Apply the 3 `.yaml` files after you have adapted them:

```bash
$ kubectl apply --validate -f k8s/namespace.yaml -f k8s/rbac.yaml -f k8s/deployment.yaml
namespace/pod-cleanup created
serviceaccount/pod-cleanup-operator created
clusterrole.rbac.authorization.k8s.io/pod-cleanup-operator created
clusterrolebinding.rbac.authorization.k8s.io/pod-cleanup-operator created
deployment.apps/pod-cleanup-operator created
```

### Command Line Arguments

| Argument                         | Default Value                | Example                           | Purpose                                                                                                                                                                                                      |
|----------------------------------|------------------------------|-----------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `-n` or <br> `--namespace`       |                              | `default`                         | Restrict the filter to just a single namespace. The default (no value) means _all namespaces_.                                                                                                               |
| `-u` or <br> `--user`            |                              |                                   | Limit the scope to only user namespaces and exclude `kube-system` objects                                                                                                                                    |
| `-g` or <br> `--graceperiod`     | `300`                        | `60`                              | How many seconds a pod has to be in the given state(s) to be considered for deletion.                                                                                                                        |
| `-l` or <br> `--label-selector`  | `'{}'`                       | `'{"app": "colortransfer-api"}'`  | Restrict the filter to just Pods and Jobs that match the [label selector](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/). _Note that the argument value needs to be valid JSON!_ |
| `--lifetime-annotation`          | `pod.kubernetes.io/lifetime` |                                   | The pod annotation to specify the maximum lifetime.                                                                                                                                                          |
| `--lifetime-max-kills`           | `1`                          |                                   | How many expired pods to terminate per run.                                                                                                                                                                  |
| `--quiet`                        |                              |                                   | Be more quiet and only print output when actually deleting pods.                                                                                                                                             |
| `--interval`                     | `60`                         |                                   | Seconds to wait between runs.                                                                                                                                                                                |
| `--dry-run`                      |                              |                                   | If the `--dry-run` flag is set, no actual deletion is performed. This can be used for testing.                                                                                                               |

In addition to the parameters above, the application takes 1 or more status arguments that filter the set of pods to be
deleted based on their current state. Each of those arguments can either just be
[a status](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) or a combination of status and reason of Pods
and Jobs that should be considered for deletion.

For example, passing `Failed` and `Succeeded` as arguments, would delete all pods that are in the `Failed` or `Succeeded`
state, regardless of their termination reason. Passing `Failed:Shutdown` as an argument would delete pods that are in `Failed`
state and have their termination reason set to `Shutdown`.

### Additional Reading

- [Managing Service Accounts](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/)
- [Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)

## 👩🏼‍💻 Running Locally

The Python script can use either a Service Account for authenticatiob (when deployed in Kubernetes) or your local
`~/.kube/config` file when running locally.

Make sure you have switched to the correct project and cluster and your `kubectl` is configured. Then, simply run
the `cleaner.py` script with the desired arguments:

```bash
$ python3 cleaner.py --graceperiod 60 --dry-run Failed:Shutdown
Pod Cleanup Operator. Version: 0.x, Commit: main, Build Date: 2021-07-06T13:36:10.700541+00:00
Using local ~/.kube/config for authentication
Deleted 0 pods and 0 jobs.
```

Alternatively, you can also use your own Service Account for authentication:

```bash
$ gcloud auth activate-service-account --key-file=<path to your generated json file>
GOOGLE_APPLICATION_CREDENTIALS=./serviceaccount.json python3 cleaner.py --graceperiod 60 --dry-run Failed:Shutdown
```

## 🤔 What is a Kubernetes Operator?

A Kubernetes operator is an application-specific controller that extends the functionality of
the Kubernetes API to create, configure, and manage instances of complex applications on behalf
of a Kubernetes user.

