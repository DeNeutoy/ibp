from graphviz import Digraph
import torch
import numpy as np
from torch.autograd import Variable, Function

EPS = 1e-16

def visualize_A(A):
    """
    Assume that A can be reshaped into 6 (6, 6) images
    """
    from matplotlib import pyplot as plt
    from matplotlib.pyplot import subplots
    a, b = A.min(), A.max()
    fig, axes = subplots(3, 2)
    for i, ax in enumerate(axes.reshape(-1)):
        im = ax.imshow(A.reshape(6, 6, 6)[i], interpolation=None, cmap='gray', vmin=a, vmax=b)
        ax.set_title(str(i + 1))
        ax.set_xticks([])
        ax.set_yticks([])
    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.5)
    plt.show()

def visualize_A_save(A, iter):
    from matplotlib import pyplot as plt
    from matplotlib.pyplot import subplots
    a, b = A.min(), A.max()
    fig, axes = subplots(3, 2)
    for i, ax in enumerate(axes.reshape(-1)):
        im = ax.imshow(A.reshape(6, 6, 6)[i], interpolation=None, cmap='gray', vmin=a, vmax=b)
        ax.set_title(str(i + 1))
        ax.set_xticks([])
        ax.set_yticks([])
    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.5)
    plt.savefig("features_{}.png".format(iter), dpi=300)

def visualize_nu_save(nu, iter):
    import seaborn as sns
    from matplotlib import pyplot as plt
    from matplotlib.pyplot import subplots
    plt.figure()
    sns.distplot(nu.reshape((-1,)), kde=False)
    plt.savefig("nu_{}.png".format(iter), dpi=300)

def inverse_softplus(x):
    return x + (1. - (-1. * x).exp() + EPS).log()

def iter_graph(root, callback):
    queue = [root]
    seen = set()
    while queue:
        fn = queue.pop()
        if fn in seen:
            continue
        seen.add(fn)
        for next_fn, _ in fn.next_functions:
            if next_fn is not None:
                queue.append(next_fn)
        callback(fn)

def register_hooks(var):
    fn_dict = {}
    def hook_cb(fn):
        def register_grad(grad_input, grad_output):
            fn_dict[fn] = grad_input
        fn.register_hook(register_grad)
    iter_graph(var.grad_fn, hook_cb)

    def is_bad_grad(grad_output):
        if grad_output is None:
            return False
        grad_output = grad_output.data
        return grad_output.ne(grad_output).any() or grad_output.gt(1e6).any()

    def make_dot():
        node_attr = dict(style='filled',
                        shape='box',
                        align='left',
                        fontsize='12',
                        ranksep='0.1',
                        height='0.2')
        dot = Digraph(node_attr=node_attr, graph_attr=dict(size="12,12"))

        def size_to_str(size):
            return '('+(', ').join(map(str, size))+')'

        def build_graph(fn):
            if hasattr(fn, 'variable'):  # if GradAccumulator
                u = fn.variable
                node_name = 'Variable\n ' + size_to_str(u.size())
                dot.node(str(id(u)), node_name, fillcolor='lightblue')
            else:
                assert fn in fn_dict, fn
                fillcolor = 'white'
                if any(is_bad_grad(gi) for gi in fn_dict[fn]):
                    fillcolor = 'red'
                dot.node(str(id(fn)), str(type(fn).__name__), fillcolor=fillcolor)
            for next_fn, _ in fn.next_functions:
                if next_fn is not None:
                    next_id = id(getattr(next_fn, 'variable', next_fn))
                    dot.edge(str(next_id), str(id(fn)))
        iter_graph(var.grad_fn, build_graph)

        return dot

    return make_dot