import { useEffect, useState } from "react";
import { Copy, PlugsConnected, X } from "@phosphor-icons/react";
import { api } from "./api";

type Connection = {id: string; name: string; scopes: string[]};
export function AgentPanel({sessionId, command, onClose, onCopySelection}: {sessionId?: string; command?: {command: string; args: string[]}; onClose: () => void; onCopySelection: () => void}) {
  const [connections, setConnections] = useState<Connection[]>([]), [error, setError] = useState("");
  const config = JSON.stringify({mcpServers: {biopipe: command || {command: "biopipe", args: ["mcp"]}}}, null, 2);
  const refresh = () => api.agent<Connection[]>("/connections").then(setConnections).catch(error => setError((error as Error).message));
  useEffect(() => {void refresh(); const timer = setInterval(() => void refresh(), 2000); return () => clearInterval(timer);}, []);
  return <div className="agent-overlay" role="presentation" onMouseDown={e => {if(e.target === e.currentTarget) onClose();}}>
    <section className="agent-panel" role="dialog" aria-modal="true" aria-label="连接自己的 Agent">
      <header><div className="agent-heading"><PlugsConnected size={24}/><div><h2>连接自己的 Agent</h2><p>让你的助手读取选区、生成路线、协作编辑。</p></div></div><button className="icon-button" aria-label="关闭 Agent 面板" onClick={onClose}><X size={18}/></button></header>
      <p>在已安装 BioPipe CLI 的环境中，将下面的配置添加到支持 MCP 的客户端。提问时，助手可读取最新选区。</p>
      <pre>{config}</pre>
      <div className="agent-actions"><button className="subtle-button" onClick={() => {void navigator.clipboard.writeText(config).catch(error=>setError(String(error)));}}><Copy size={15}/>复制 MCP 配置</button><button className="subtle-button" onClick={onCopySelection}>复制选区上下文</button></div>
      <p className="agent-note">画布修改可撤销。运行分析需在 MCP 启动参数中添加 <code>--allow-run</code>。无 CLI 的环境可使用已配置的 Python 执行 <code>-m biopipe mcp</code>。</p>
      <div className="agent-session"><span>当前画布会话</span><code>{sessionId || "连接中…"}</code></div>
      <h3>已连接客户端</h3>
      {!connections.length && <p className="agent-note">等待你的客户端连接。</p>}
      {connections.map(connection => <div className="agent-connection" key={connection.id}><div><strong>{connection.name}</strong><span>{connection.scopes.join(" · ")}</span></div><button className="subtle-button" onClick={() => {void api.agent("/connections/revoke", {id: connection.id}).then(refresh).catch(error=>setError(String(error)));}}>断开</button></div>)}
      {error && <p role="alert" className="field-error">{error}</p>}
    </section>
  </div>;
}
