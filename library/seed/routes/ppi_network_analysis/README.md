# PPI network analysis route

## Data

| Item | Value |
| --- | --- |
| Source | STRING v12.0, Escherichia coli K-12, CRP regulon with 100 added interaction partners |
| Query | `identifiers=crp&species=511145&add_nodes=100&required_score=400` |
| Nodes / edges | 101 / 919 |
| Input file | `input/network_edges.csv` (919 rows, columns `edge_id,node_a,node_b,score`) |
| sha256 | `d91dfe2da126dece5cfbd40230c20843ae407dfc7614e7b980bec6eb935aee48` |

The edge list is undirected; STRING scores are kept in the CSV but the current
operators treat every edge as weight 1 (documented limitation below).

## Steps

| # | Operator | Time (s) |
| --- | --- | --- |
| 1 | `network_summary` | 0.008 |
| 2 | `export_results` (summary) | 0.001 |
| 3 | `network_centrality` | 0.042 |
| 4 | `export_results` (centrality) | 0.002 |
| 5 | `network_communities` | 3.073 |
| 6 | `export_results` (communities) | 0.001 |

Total `3.1272 s` on WSL (Python 3.12, single core).

## Results

`network_summary`: nodes 101, edges 919, density 0.1819802, components 1,
largest component 101, diameter 2, average degree 18.1980198,
clustering coefficient 0.598534, degree assortativity -0.1585177.

`network_centrality`: 101 rows with degree, betweenness, closeness,
eigenvector and pagerank. Highest pagerank: `crp` 0.0557800, `lacZ`
0.0296186, `rpoS` 0.0289984.

`network_communities`: three communities of 38, 22 and 41 nodes;
modularity 0.2684951116615615.

## Oracles

| Oracle | Version | Quantity | Result |
| --- | --- | --- | --- |
| networkx | 3.x (Python) | summary 9 metrics | max abs 1.39e-16 |
| networkx | 3.x | centrality 5 metrics | max abs 3.45e-12 (eigenvector 1.0e-14, pagerank 3.45e-12) |
| networkx | 3.x | greedy modularity partition | identical partition, modularity diff 0 |
| base R | 4.3.3 | summary 9 metrics | max abs 1.11e-16 |
| base R | 4.3.3 | modularity of exported partition | 0.2684951 (diff 5.6e-8 from text) |

## Interpretation

The CRP regulon network is dense and tightly connected (one component,
diameter 2), so the three detected communities describe functional modules
rather than disconnected clusters. `crp` has the highest pagerank, consistent
with it being the regulon hub. This is a topology statement only: the route
does not infer regulatory direction or causality from undirected edges.

## Limitations

- Edges are treated as unweighted; STRING confidence scores are parsed but not
  used by centrality or modularity.
- The graph is forced undirected; directionality of regulation is lost.
- `network_communities` implements greedy modularity (Clauset-Newman-Moore),
  not exhaustive modularity optimisation; small networks can have a different
  optimum.
- `diameter` is measured on the largest connected component; disconnected
  components are summarised only by count and size.
- Self loops are skipped.
