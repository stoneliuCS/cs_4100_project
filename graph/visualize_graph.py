import osmnx as ox
import numpy as np
import matplotlib.pyplot as plt
from graph.create_graph import coerce_kde_value
from io import BytesIO
import matplotlib.image as mpimg


def get_path_bbox(G, path_nodes, buffer=200):
    """
    Bounding box (minx, maxx, miny, maxy) around the path, with a buffer
    in the graph’s units (meters if G is projected).
    """
    xs = [G.nodes[n]["x"] for n in path_nodes]
    ys = [G.nodes[n]["y"] for n in path_nodes]

    minx, maxx = min(xs) - buffer, max(xs) + buffer
    miny, maxy = min(ys) - buffer, max(ys) + buffer

    return minx, maxx, miny, maxy


def plot_path_with_risk(G, path_nodes, risk_attr: str, bbox=None):
    kde_vals = np.array(
        [
            coerce_kde_value(d.get(risk_attr, 0.0))
            for _, _, _, d in G.edges(keys=True, data=True)
        ]
    )
    vmax = kde_vals.max() if kde_vals.size > 0 else 0
    if vmax > 0:
        kde_norm = kde_vals / vmax
    else:
        kde_norm = kde_vals

    cmap = plt.cm.inferno
    edge_colors = [cmap(v) for v in kde_norm]

    fig, ax = ox.plot_graph(
        G,
        node_size=0,
        edge_color=edge_colors,
        edge_linewidth=0.6,
        bgcolor="white",
        show=False,
        close=False,
    )

    if bbox is not None:
        minx, maxx, miny, maxy = bbox
        ax.set_xlim(minx, maxx)
        ax.set_ylim(miny, maxy)

    ox.plot_graph_route(
        G,
        path_nodes,
        route_linewidth=3,
        route_color="cyan",
        orig_dest_node_size=30,
        orig_dest_node_color="red",
        ax=ax,
        show=False,
        close=False,
    )

    return fig, ax


def plot_kde_graph(G, kde_attr: str, bbox=None):
    kde_vals = np.array(
        [
            coerce_kde_value(d.get(kde_attr, 0.0))
            for _, _, _, d in G.edges(keys=True, data=True)
        ]
    )
    vmax = kde_vals.max() if kde_vals.size > 0 else 0
    if vmax > 0:
        kde_norm = kde_vals / vmax
    else:
        kde_norm = kde_vals

    cmap = plt.cm.inferno
    edge_colors = [cmap(v) for v in kde_norm]

    fig, ax = ox.plot_graph(
        G,
        node_size=0,
        edge_color=edge_colors,
        edge_linewidth=0.6,
        bgcolor="white",
        show=False,
        close=False,
    )

    if bbox is not None:
        minx, maxx, miny, maxy = bbox
        ax.set_xlim(minx, maxx)
        ax.set_ylim(miny, maxy)

    return fig, ax


def show_path_and_kde_full_and_zoom(
    G,
    path_nodes,
    risk_attr,
    kde_attr,
    buffer=200,
    hour_label: str | None = None,
):
    bbox = get_path_bbox(G, path_nodes, buffer=buffer)

    path_full_fig, _ = plot_path_with_risk(G, path_nodes, risk_attr, bbox=None)
    kde_full_fig, _ = plot_kde_graph(G, kde_attr, bbox=None)

    path_zoom_fig, _ = plot_path_with_risk(G, path_nodes, risk_attr, bbox=bbox)
    kde_zoom_fig, _ = plot_kde_graph(G, kde_attr, bbox=bbox)

    def fig_to_img(fig):
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        buf.seek(0)
        img = mpimg.imread(buf)
        plt.close(fig)
        return img

    img_path_full = fig_to_img(path_full_fig)
    img_kde_full = fig_to_img(kde_full_fig)
    img_path_zoom = fig_to_img(path_zoom_fig)
    img_kde_zoom = fig_to_img(kde_zoom_fig)

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    axes[0, 0].imshow(img_path_full)
    axes[0, 0].set_title("Path with Risk (Full)", fontsize=11)
    axes[0, 0].axis("off")

    axes[0, 1].imshow(img_kde_full)
    axes[0, 1].set_title("KDE Graph (Full)", fontsize=11)
    axes[0, 1].axis("off")

    axes[1, 0].imshow(img_path_zoom)
    axes[1, 0].set_title("Path with Risk (Zoomed)", fontsize=11)
    axes[1, 0].axis("off")

    axes[1, 1].imshow(img_kde_zoom)
    axes[1, 1].set_title("KDE Graph (Zoomed)", fontsize=11)
    axes[1, 1].axis("off")

    if hour_label is not None:
        fig.suptitle(
            f"Crime Risk and Route for Hour {hour_label}",
            fontsize=16,
            fontweight="bold",
            y=0.98,
        )

        plt.tight_layout(rect=[0, 0, 1, 0.95])
    else:
        plt.tight_layout()

    plt.show()

    return fig
