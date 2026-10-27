import { memo, useEffect } from "react";
import {
  Handle,
  Position,
  useUpdateNodeInternals,
  useViewport,
} from "@xyflow/react";
import type { Node, NodeProps } from "@xyflow/react";
import { Check, CircleNotch, WarningCircle } from "@phosphor-icons/react";
import { OperatorArtwork } from "./OperatorArtwork";
import { displayTitle, inputCount, outputCount } from "./graph";
import { NODE_LAYOUT, portOffset, portRowHeight } from "./nodeLayout";
import type { GraphNode, Operator, NodeContracts, ContractCheck } from "./types";
import { InfoPort } from "./InfoPort";

export type BlockData = {
  model: GraphNode;
  spec?: Operator;
  status?: string;
  order?: number;
  invalid?: boolean;
  busy: boolean;
  contracts?: NodeContracts;
  contractChecks?: ContractCheck[];
  [key: string]: unknown;
};
export type Block = Node<BlockData, "block">;
export const WorkflowNode = memo(function WorkflowNode({
  data,
  selected,
}: NodeProps<Block>) {
  const { model: node, spec, order, status, invalid, busy } = data;
  const title = displayTitle(node, spec);
  const inputs = inputCount(node, spec),
    outputs = outputCount(node, spec);
  const source = node.kind === "source";
  const { zoom } = useViewport();
  const overview = zoom < 0.55;
  const updateInternals = useUpdateNodeInternals();
  useEffect(() => {
    updateInternals(node.id);
  }, [node.id, inputs, outputs, updateInternals]);
  const subtitle = source
    ? node.source?.path.split(/[\\/]/).pop() || "选择一个数据文件"
    : node.operator === "pca"
      ? `${node.params.n_components ?? 10} 个主成分 · ${node.params.dim}`
      : node.operator === "missing"
        ? `缺失比例 ≤ ${Number(node.params.threshold ?? 0.1) * 100}%`
        : typeof node.params.method === "string" ? node.params.method : "";
  return (
    <div
      className={`workflow-node ${overview ? "overview" : ""} ${source ? "source-node" : ""} ${node.kind === "route" ? "route-node" : ""} ${selected ? "is-selected" : ""} ${invalid ? "is-invalid" : ""} ${status || ""}`}
      style={{ width: NODE_LAYOUT.width }}
    >
      <InfoPort direction="input" height={portRowHeight(inputs)} source={source}
        labels={node.route?.graph.interface?.inputs.map(p=>p.label)}
        ports={data.contracts?.inputs} checks={data.contractChecks}
        hint={source ? (data.remote ? '服务器数据' : "本地数据") : inputs > 1 ? `${inputs} 个输入` : "IN"}>
        {Array.from({ length: inputs }, (_, index) => (
          <Handle
            key={index}
            id={`in-${index}`}
            type="target"
            position={Position.Left}
            style={{ top: portOffset(inputs, index), left: -5 }}
            isConnectable={!busy}
            title={node.route?.graph.interface?.inputs[index]?.label || `输入 ${index + 1}`}
          />
        ))}
      </InfoPort>
      <div className="node-body" title={spec?.description} style={{ minHeight: NODE_LAYOUT.bodyHeight }}>
        <div
          className={`node-icon category-${source ? "source" : spec?.category === "统计分析" ? "analysis" : spec?.category === "可视化" ? "plot" : "data"}`}
        >
          <OperatorArtwork spec={spec} source={source}/>
        </div>
        <div className="node-copy">
          <strong
            title={title}
            style={overview ? { fontSize: Math.min(36, 10 / zoom) } : undefined}
          >
            {title}
          </strong>
          {subtitle && <p>{subtitle}</p>}
          {spec?.supported_systems?.join(',') === 'linux' && <span className="platform-badge" title="需要 Linux 运行环境">Linux</span>}
        </div>
        <span className="node-state">
          {status === "finished" ? (
            <Check size={15} weight="bold" />
          ) : status === "running" ? (
            <CircleNotch size={15} className="spin" />
          ) : invalid ? (
            <WarningCircle size={17} />
          ) : order ? (
            String(order).padStart(2, "0")
          ) : null}
        </span>
      </div>
      <InfoPort direction="output" height={portRowHeight(outputs)} ports={data.contracts?.outputs}
        labels={node.route?.graph.interface?.outputs.map(p=>p.label)}
        hint={source
            ? node.source?.dims.join(" × ")
            : spec?.resources.memory_modes.includes("stream")
              ? "可分块"
              : spec?.output_parameter
                ? String(node.params.output || node.id)
                : outputs
                  ? "OUT"
                  : "终点"}>
        {Array.from({ length: outputs }, (_, index) => (
          <Handle
            key={index}
            id={outputs === 1 ? "out" : `out-${index}`}
            type="source"
            position={Position.Right}
            style={{ top: portOffset(outputs, index), right: -5 }}
            isConnectable={!busy}
            title={node.route?.graph.interface?.outputs[index]?.label || `输出 ${index + 1}`}
          />
        ))}
      </InfoPort>
    </div>
  );
});
