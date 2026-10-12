import {describe, it, expect} from "vitest";
import {copyFragment, parseFragment, pasteFragment} from "./editing";
import type {Graph} from "./types";
import {runSignature} from "./graph";

const graph: Graph = {schema_version:2,name:"Example",base_dir:".",memory:{enabled:true},nodes:[
  {id:"data",kind:"source",title:"Data",position:{x:0,y:0},params:{},input_count:0},
  {id:"pca",kind:"operator",operator:"pca",title:"PCA",position:{x:280,y:0},params:{output:"pcs",dim:"feature"},input_count:1},
  {id:"report",kind:"operator",operator:"describe",title:"Summary",position:{x:560,y:0},params:{},input_count:1}],
  edges:[{id:"one",source:"data",target:"pca",sourceHandle:"out",targetHandle:"in-0"},{id:"two",source:"pca",target:"report",sourceHandle:"out",targetHandle:"in-0"}]};
describe("copy and paste subgraphs",()=>{
  it("keeps internal branches, allocates independent aliases and never copies external wires",()=>{
    const fragment=parseFragment(JSON.stringify(copyFragment(graph,["data","pca"])));
    const first=pasteFragment(graph,fragment);
    const second=pasteFragment(first.graph,fragment);
    expect(second.graph.nodes).toHaveLength(7);
    expect(second.graph.edges).toHaveLength(4);
    expect(new Set(second.graph.nodes.map(n=>n.id)).size).toBe(7);
    expect(second.graph.nodes[4].params.output).not.toBe("pcs");
    expect(second.graph.edges[3].source).toBe(second.ids[0]);
    expect(second.graph.edges[3].target).toBe(second.ids[1]);
    expect(graph.nodes).toHaveLength(3);
  });
  it("preserves embedded route snapshots across canvases without sharing mutable objects",()=>{
    const withRoute=structuredClone(graph);
    withRoute.nodes.push({id:"route1",kind:"route",title:"Reusable",position:{x:500,y:300},params:{},input_count:1,route:{id:"route_123456789abc",version:1,name:"Reuse",graph:structuredClone(graph)}});
    const pasted=pasteFragment(graph,copyFragment(withRoute,["route1"]));
    expect(pasted.graph.nodes[3].route?.version).toBe(1);
    const signature=runSignature(pasted.graph);
    pasted.graph.nodes[3].route!.graph.nodes[1].params.dim="sample";
    expect(runSignature(pasted.graph)).not.toBe(signature);
    expect(withRoute.nodes[3].route!.graph.nodes[1].params.dim).toBe("feature");
  });
  it("rejects non-BioPipe clipboard data",()=>expect(()=>parseFragment('{"nodes":[]}')).toThrow());
  it("preserves the input file when copying across different relative base directories",()=>{
    const source=structuredClone(graph), target=structuredClone(graph);
    source.base_dir="experiments/one"; target.base_dir="experiments/two";
    source.nodes[0].source={path:"data/counts.csv",dims:["sample","feature"],labels:{},args:{}};
    const pasted=pasteFragment(target,copyFragment(source,["data"]));
    expect(pasted.graph.nodes[3].source?.path).toBe("../one/data/counts.csv");
    expect(source.nodes[0].source.path).toBe("data/counts.csv");
  });
});
