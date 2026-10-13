import { PluginPanel } from "./PluginPanel";
import {
  Component,
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { CSSProperties, ErrorInfo, ReactNode } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  SelectionMode,
} from "@xyflow/react";
import type { Connection, NodeChange, EdgeChange } from "@xyflow/react";
import {
  ArrowCounterClockwise,
  ArrowClockwise,
  ArrowDown,
  ArrowUp,
  ArrowsOut,
  CaretDown,
  Check,
  CheckCircle,
  CircleNotch,
  Dna,
  FloppyDisk,
  GearSix,
  Lightning,
  Keyboard,
  List,
  MagnifyingGlass,
  Minus,
  Plus,
  Rows,
  SidebarSimple,
  SquaresFour,
  Stop,
  X,
  Stack,
  FolderOpen,
  Copy,
  Clipboard,
  PauseCircle,
  Package,
  PlayCircle,
  Trash,
} from "@phosphor-icons/react";
import { api, ApiError, downloadText } from "./api";
import { CanvasBridge } from "./agentBridge";
import type { AgentState } from "./agentBridge";
import { AgentPanel } from "./AgentPanel";
import {
  autoLayout,
  clone,
  displayTitle,
  executionOrder,
  inputCount,
  makeNode,
  normalizeGraph,
  outputCount,
  runSignature,
  specFor,
  wouldCycle,
  makeRouteNode,
  routeSpec,
  retainedOutputs,
} from "./graph";
import { copyFragment, parseFragment, pasteFragment } from "./editing";
import type { Fragment } from "./editing";
import { DocumentTabs } from "./DocumentTabs";
import { SaveWorkflowDialog, WorkflowPicker } from "./RouteDialogs";
import { WorkflowNode } from "./WorkflowNode";
import { WorkflowEdge } from "./WorkflowEdge";
import type { Block } from "./WorkflowNode";
import { Inspector } from "./Inspector";
import { HelpTip } from "./HelpTip";
import { LibrarySection } from "./LibrarySection";
import { Results, statusLabel } from "./Results";
import { OperatorIcon } from "./icons";
import { OperatorArtwork } from "./OperatorArtwork";
import { PanelResizeHandle } from "./PanelResizeHandle";
import { automaticPanels, panelLimits, panelMaximum, resolvePanels } from "./panelLayout";
import type { PanelSide, PanelWidths } from "./panelLayout";
import { AppearanceMenu } from "./AppearanceMenu";
import { NODE_LAYOUT, portRowHeight } from "./nodeLayout";
import { contractSignature } from "./contracts";
import type {
  Bootstrap,
  Graph,
  GraphEdge,
  GraphNode,
  Job,
  RunEvent,
  ContractAnalysis,
  WorkspaceDocument,
  Workspace,
  RouteDefinition,
  SavedWorkflow,
  LibraryState,
  LibraryAction,
} from "./types";

const DRAFT_KEY = "biopipe-studio-draft-v1";
const nodeTypes = { block: WorkflowNode };
const edgeTypes = { workflow: WorkflowEdge };
const emptyGraph: Graph = {
  schema_version: 1,
  name: "我的工作流",
  base_dir: ".",
  nodes: [],
  edges: [],
  memory: { enabled: true, auto_spill: true },
};
const LoadingSkeleton = memo(function LoadingSkeleton() {
  return (
    <div className="boot-skeleton" aria-hidden="true">
      <div />
      <div>
        <span />
        <span />
        <span />
      </div>
      <div />
    </div>
  );
});
class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Studio UI error", error, info.componentStack);
  }
  render() {
    return this.state.failed ? (
      <div className="boot-state" role="status" aria-live="polite">
        <Dna size={36} />
        <h1>界面需要重新加载</h1>
        <p>草稿已保存在此浏览器。可以重新加载，或恢复示例画布。</p>
        <button className="primary-button" onClick={() => location.reload()}>
          重新加载
        </button>
        <button
          className="text-button"
          onClick={() => {
            localStorage.removeItem(DRAFT_KEY);
            location.reload();
          }}
        >
          恢复示例
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
function Studio() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null),
    [bootError, setBootError] = useState("");
  const [graph, setGraph] = useState<Graph>(emptyGraph),
    graphRef = useRef(graph);
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([]), documentsRef = useRef<WorkspaceDocument[]>([]);
  const [activeId, setActiveId] = useState(""), activeIdRef = useRef("");
  const closedDocuments = useRef<WorkspaceDocument[]>([]);
  const documentHistory = useRef<Record<string, {past: Graph[]; future: Graph[]; selection: string[]}>>({});
  const agentBridge = useRef<CanvasBridge | null>(null);
  const [agentReady, setAgentReady] = useState(false), [agentPanel, setAgentPanel] = useState(false);
  const [routes, setRoutes] = useState<RouteDefinition[]>([]);
  const [pluginsOpen, setPluginsOpen] = useState(false);
  const [libraryState, setLibraryState] = useState<LibraryState>({disabled: [], hidden: []});
  const [showHidden, setShowHidden] = useState(false);
  const [panelWidths, setPanelWidths] = useState<PanelWidths>(automaticPanels);
  const [windowWidth, setWindowWidth] = useState(() => window.innerWidth);
  const [resizingPanel, setResizingPanel] = useState(false);
  const displayedPanels = resolvePanels(panelWidths, windowWidth);
  useEffect(() => {
    const resize = () => setWindowWidth(window.innerWidth);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  function resizePanel(side: PanelSide, width: number | null) {
    setPanelWidths(value => ({ ...value, [side]: width })); setSaved(false);
  }
  const [picker, setPicker] = useState<"open" | "register" | null>(null);
  const [saveDialog, setSaveDialog] = useState<Graph | null>(null);
  const [contextMenu, setContextMenu] = useState<{x: number; y: number; route?: RouteDefinition; nodeId?: string; libraryKey?: string} | null>(null);
  const clipboard = useRef<Fragment | null>(null), routeImport = useRef<HTMLInputElement>(null);
  const [past, setPast] = useState<Graph[]>([]),
    [future, setFuture] = useState<Graph[]>([]);
  const [selected, setSelected] = useState<string | null>("pca"),
    [selection, setSelection] = useState<string[]>(["pca"]),
    [selectedEdges, setSelectedEdges] = useState<string[]>([]),
    [search, setSearch] = useState("");
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [contractResult, setContractResult] = useState<{ key: string; value: ContractAnalysis } | null>(null);
  const connecting = useRef(false);
  const contractKey = contractSignature(graph);
  const contracts = contractResult?.key === contractKey ? contractResult.value : undefined;
  const [inspected, setInspected] = useState<string | null>(null);
  const [settings, setSettings] = useState(false),
    [libraryOpen, setLibraryOpen] = useState(false),
    [inspectorOpen, setInspectorOpen] = useState(false);
  const [toast, setToast] = useState<{
      message: string;
      type: "error" | "success";
    } | null>(null),
    [invalid, setInvalid] = useState<string | undefined>();
  const [action, setAction] = useState(""),
    [saved, setSaved] = useState(false),
    [tab, setTab] = useState("results");
  const [job, setJob] = useState<Job | null>(null),
    [history, setHistory] = useState<Job[]>([]),
    [events, setEvents] = useState<RunEvent[]>([]);
  // React Flow's measurements preserve port bounds across controlled-node updates.
  // They belong to the current view, not the saved workflow or its run identity.
  const [nodeMeasurements, setNodeMeasurements] = useState<
    Record<string, { width: number; height: number }>
  >({});
  const [exportOpen, setExportOpen] = useState(false),
    [importBase, setImportBase] = useState(".");
  const [resultsExpanded, setResultsExpanded] = useState(false),
    [resultsCollapsed, setResultsCollapsed] = useState(true);
  const importInput = useRef<HTMLInputElement>(null),
    dragOrigin = useRef<Graph | null>(null),
    canvas = useRef<HTMLDivElement>(null);
  const flow = useReactFlow<Block>(),
    busy = job?.status === "running";
  const catalog = bootstrap?.catalog || {
    schema_version: 1 as const,
    operators: [],
  };
  const inspectNode = useCallback((id: string | null) => {
    setSelected(id);
    setInspected(id);
    setSettings(false);
    setInspectorOpen(true);
    setLibraryOpen(false);
  }, []);
  const closeInspector = useCallback(() => {
    setInspected(null);
    setSettings(false);
    setInspectorOpen(false);
  }, []);
  useEffect(() => {
    if (inspected && !graph.nodes.some((node) => node.id === inspected))
      closeInspector();
  }, [graph.nodes, inspected, closeInspector]);

  const notify = useCallback(
    (message: string, type: "error" | "success" = "error") =>
      setToast({ message, type }),
    [],
  );
  useEffect(() => {
    if (!bootstrap) return;
    let active = true;
    const timer = setTimeout(() => {
      const snapshot = graphRef.current;
      void api.contracts(snapshot).then(value => {
        if (active && contractSignature(graphRef.current) === contractKey)
          setContractResult({ key: contractKey, value });
      }).catch(error => { if (active) notify(`契约检查：${(error as Error).message}`); });
    }, 180);
    return () => { active = false; clearTimeout(timer); };
  }, [bootstrap, contractKey, notify]);
  const putGraph = useCallback((next: Graph) => {
    graphRef.current = next;
    setGraph(next);
    const updated = documentsRef.current.map(doc => doc.id === activeIdRef.current ? {...doc, graph: next} : doc);
    documentsRef.current = updated; setDocuments(updated);
    setSaved(false);
    setInvalid(undefined);
  }, []);
  const commit = useCallback(
    (next: Graph | ((current: Graph) => Graph)) => {
      const previous = graphRef.current;
      const value = typeof next === "function" ? next(clone(previous)) : next;
      if (JSON.stringify(previous) === JSON.stringify(value)) return;
      setPast((items) => [...items.slice(-29), clone(previous)]);
      setFuture([]);
      putGraph(value);
    },
    [putGraph],
  );
  const fit = useCallback(() => {
    requestAnimationFrame(() => {
      if (!canvas.current) return;
      const bounds = canvas.current.getBoundingClientRect();
      const toolbar = canvas.current
        .querySelector(".canvas-header")
        ?.getBoundingClientRect();
      const controls = canvas.current
        .querySelector(".canvas-bottomline")
        ?.getBoundingClientRect();
      // Fit into the clear area between floating panels, while the canvas
      // itself remains continuous underneath them.
      void flow.fitView({
        padding: {
          top: `${Math.max(24, (toolbar?.bottom ?? bounds.top) - bounds.top + 24)}px`,
          bottom: `${Math.max(24, bounds.bottom - (controls?.top ?? bounds.bottom) + 24)}px`,
          left: `${Math.max(24, (toolbar?.left ?? bounds.left) - bounds.left + 24)}px`,
          right: `${Math.max(24, bounds.right - (toolbar?.right ?? bounds.right) + 24)}px`,
        },
        duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? 0
          : 230,
        maxZoom: 1,
      });
    });
  }, [flow]);
  function captureWorkspace(): Workspace {
    return {schema_version: 1, active_id: activeIdRef.current, documents: documentsRef.current.map(doc => doc.id === activeIdRef.current ? {...doc, graph: graphRef.current, viewport: flow.getViewport()} : doc), closed_documents: closedDocuments.current, panel_widths: panelWidths};
  }
  const captureRef = useRef(captureWorkspace);
  captureRef.current = captureWorkspace;
  const presenceRef = useRef(() => ({document_id: activeIdRef.current, nodes: selection, edges: selectedEdges,
    inspected_node: inspected, focused_field: document.activeElement?.id || "", viewport: flow.getViewport()}));
  presenceRef.current = () => ({document_id: activeIdRef.current, nodes: selection, edges: selectedEdges,
    inspected_node: inspected, focused_field: document.activeElement?.id || "", viewport: flow.getViewport()});
  const receiveAgentRef = useRef((state: AgentState) => {void state;});
  receiveAgentRef.current = state => {
    const pages = state.workspace.documents.map(doc => ({...doc, graph: normalizeGraph(doc.graph)}));
    const active = state.workspace.active_id;
    closedDocuments.current = state.workspace.closed_documents || [];
    if (active !== activeIdRef.current) activatePage(active, pages);
    else {
      documentsRef.current = pages; setDocuments(pages);
      const next = pages.find(doc => doc.id === active)!.graph;
      graphRef.current = next; setGraph(next);
    }
    const item = state.history[active] || {undo: 0, redo: 0};
    setPast(Array(item.undo).fill(graphRef.current)); setFuture(Array(item.redo).fill(graphRef.current));
    setSaved(true);
  };
  const readyForAgent = !!bootstrap;
  useEffect(() => {
    if (!readyForAgent) return;
    let alive = true, timer: ReturnType<typeof setTimeout>;
    const bridge = new CanvasBridge(() => captureRef.current(), () => presenceRef.current(),
      state => receiveAgentRef.current(state), message => notify(message));
    agentBridge.current = bridge;
    const tick = async () => {
      try {await bridge.tick();} catch (error) {if (alive) notify((error as Error).message);}
      if (alive) timer = setTimeout(() => void tick(), 350);
    };
    void bridge.start().then(() => {if (alive) {setAgentReady(true); void tick();}}).catch(error => notify(`Agent 接口连接失败：${(error as Error).message}`));
    return () => {alive = false; clearTimeout(timer); bridge.stop(); if (agentBridge.current === bridge) agentBridge.current = null;};
  }, [readyForAgent, notify]);
  async function copyAgentContext() {
    try {
      const context = await agentBridge.current?.context();
      if (!context) throw Error("Agent 接口尚未就绪");
      await navigator.clipboard.writeText(JSON.stringify(context, null, 2));
      notify("已复制选区上下文，可粘贴到自己的 agent。", "success"); setContextMenu(null);
    } catch (error) {failure(error);}
  }
  function stashPage() {
    documentHistory.current[activeIdRef.current] = {past, future, selection};
    documentsRef.current = captureWorkspace().documents;
  }
  function activatePage(id: string, pages = documentsRef.current) {
    const doc = pages.find(item => item.id === id);
    if (!doc) return;
    activeIdRef.current = id; setActiveId(id);
    documentsRef.current = pages; setDocuments(pages);
    graphRef.current = doc.graph; setGraph(doc.graph);
    const editing = documentHistory.current[id];
    setPast(editing?.past || []); setFuture(editing?.future || []); setSelection(editing?.selection || []);
    setSelected(null); setSelectedEdges([]); setNodeMeasurements({}); setHoveredNode(null); setInvalid(undefined); setContractResult(null);
    closeInspector(); setContextMenu(null); setSaved(false);
    requestAnimationFrame(() => {if (doc.viewport) void flow.setViewport(doc.viewport); else fit();});
  }
  function switchPage(id: string) {if(id === activeIdRef.current) return; stashPage(); activatePage(id);}
  function openPages(items: {graph: Graph; workflow_id?: string; workflow_version?: number}[]) {
    stashPage(); const pages = [...documentsRef.current]; let focus = activeIdRef.current;
    for (const item of items) {
      const existing = item.workflow_id && pages.find(doc => doc.workflow_id === item.workflow_id && doc.workflow_version === item.workflow_version);
      if (existing) {focus = existing.id; continue;}
      if (pages.length >= 20) {notify("最多同时打开 20 个页面，请先关闭部分页面。"); break;}
      const doc = {...item, graph: normalizeGraph(clone(item.graph)), id: `page_${crypto.randomUUID()}`};
      pages.push(doc); focus = doc.id;
    }
    activatePage(focus, pages);
  }
  function newPage() {openPages([{graph: {...clone(emptyGraph), schema_version: 2, name: "未命名路线"}}]);}
  function closePage(id: string) {
    stashPage(); const index = documentsRef.current.findIndex(doc => doc.id === id);
    const doc = documentsRef.current[index]; if(!doc) return;
    closedDocuments.current = [doc, ...closedDocuments.current].slice(0, 10);
    const pages = documentsRef.current.filter(doc => doc.id !== id);
    if (!pages.length) pages.push({id: `page_${crypto.randomUUID()}`, graph: clone(emptyGraph)});
    activatePage(id === activeIdRef.current ? pages[Math.min(index, pages.length-1)].id : activeIdRef.current, pages);
  }
  function reopenPage() {
    const doc = closedDocuments.current[0]; if(!doc) return;
    if (documentsRef.current.length >= 20) return notify("最多同时打开 20 个页面。");
    stashPage(); closedDocuments.current = closedDocuments.current.slice(1); activatePage(doc.id, [...documentsRef.current, doc]);
  }
  function openRoute(route: RouteDefinition) {
    openPages([{graph: route.graph, workflow_id: route.id, workflow_version: route.version}]);
  }
  function openSaved(items: SavedWorkflow[]) {openPages(items.map(item => ({graph: item.graph, workflow_id: item.id, workflow_version: item.version})));}
  async function refreshRoutes() {
    const [registered, state] = await Promise.all([api.routes(), api.libraryState()]);
    setRoutes(registered); setLibraryState(state);
  }
  async function manageLibrary(key: string, action: LibraryAction) {
    setContextMenu(null);
    try {
      const result = await api.manageLibrary(key, action);
      setRoutes(result.routes); setLibraryState(result.state);
      notify(action === "delete" ? (key.startsWith("route_") ? "已从算子库删除，可通过 ＋ 重新添加已保存路线。" : "已从算子库删除，可在「已删除」中恢复。")
        : action === "disable" ? "算子已禁用，右键可重新启用。" : "算子已启用。", "success");
    } catch (error) {failure(error);}
  }
  function savedWorkflow(item: SavedWorkflow) {
    const pages = documentsRef.current.map(doc => doc.id === activeIdRef.current ? {...doc, graph: item.graph, workflow_id: item.id, workflow_version: item.version} : doc);
    documentsRef.current = pages; setDocuments(pages); putGraph(item.graph);
    notify(`路线已保存 · v${item.version}，可从算子库 ＋ 注册。`, "success");
  }
  async function importRoutes(files: FileList | null) {
    if (!files) return;
    try {
      const saved: SavedWorkflow[] = [];
      for (const file of Array.from(files)) {
        const graph = normalizeGraph(JSON.parse(await file.text()));
        saved.push(await api.saveWorkflow(graph));
      }
      setPicker(null); openSaved(saved); notify(`已导入 ${saved.length} 条路线。请通过算子库 ＋ 选择注册。`, "success");
    } catch(error) {failure(error);} finally {if(routeImport.current) routeImport.current.value = "";}
  }
  async function copySelection(cut = false) {
    const fragment = copyFragment(graphRef.current, selection);
    if (!fragment.nodes.length) return;
    clipboard.current = fragment;
    if (cut && !busy) deleteNodes(selection);
    try {await navigator.clipboard.writeText(JSON.stringify(fragment));} catch { /* Internal clipboard supports desktop permissions. */ }
    notify(`已${cut ? "剪切" : "复制"} ${fragment.nodes.length} 个节点及内部连线。`, "success");
    setContextMenu(null);
  }
  async function pasteSelection(duplicate = false, anchor?: {x: number; y: number}) {
    if (busy) return;
    const page = activeIdRef.current;
    try {
      let fragment = duplicate ? copyFragment(graphRef.current, selection) : clipboard.current;
      if (!duplicate) {
        try {const text = await navigator.clipboard.readText(); if(text.includes('"biopipe/graph-fragment-v1"')) fragment = parseFragment(text);} catch { /* use internal clipboard */ }
      }
      if (!fragment?.nodes.length) return notify("剪贴板中没有 BioPipe 节点。");
      if (page !== activeIdRef.current) return;
      const value = pasteFragment(graphRef.current, fragment, anchor); commit(value.graph); setSelection(value.ids); setSelected(value.ids[0] || null); setSelectedEdges([]);
      setContextMenu(null);
    } catch(error) {failure(error);}
  }
  const load = useCallback(async () => {
    setBootError("");
    try {
      const data = await api.bootstrap();
      setHistory(data.history);
      const [workspace, registered, state] = await Promise.all([api.workspace(), api.routes(), api.libraryState()]);
      setRoutes(registered);
      setLibraryState(state);
      setPanelWidths(workspace?.panel_widths || automaticPanels);
      let initial = normalizeGraph(data.demo);
      try {
        if (data.desktop) {
          if (data.draft) initial = normalizeGraph(data.draft);
        } else {
          const draft = localStorage.getItem(DRAFT_KEY);
          if (draft) initial = normalizeGraph(JSON.parse(draft));
        }
      } catch {
        notify("上次草稿无法恢复，已载入示例。");
      }
      const running = data.history.find((item) => item.status === "running");
      if (running) {
        const current = await api.job(running.id);
        setJob(current);
        if (current.graph) initial = normalizeGraph(current.graph);
      }
      if (workspace?.documents.length && workspace.documents.some(doc => doc.id === workspace.active_id)) {
        const pages = workspace.documents.map(doc => ({...doc, graph: normalizeGraph(doc.graph)}));
        closedDocuments.current = workspace.closed_documents || [];
        activatePage(workspace.active_id, pages);
        initial = pages.find(doc => doc.id === workspace.active_id)!.graph;
      } else {
        const doc = {id: `page_${crypto.randomUUID()}`, graph: initial}; activatePage(doc.id, [doc]);
      }
      const id =
        initial.nodes.find((n) => n.operator === "pca")?.id ||
        initial.nodes[0]?.id ||
        null;
      setSelected(id);
      setSelection(id ? [id] : []);
      // Publish readiness only after workspace preferences and documents have
      // hydrated. The desktop host may request an immediate save-and-close.
      setBootstrap(data);
    } catch (error) {
      setBootError((error as Error).message);
    }
  }, [fit, notify, putGraph]);
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    if (!bootstrap) return;
    let active = true;
    const refresh = () => {
      if (document.visibilityState === "hidden") return;
      void Promise.all([api.routes(), api.libraryState(), api.catalog()]).then(([value, state, latest]) => {if (active) {setRoutes(value); setLibraryState(state); setBootstrap(current => current ? {...current, catalog: latest} : current);}}).catch(() => {
        // Preserve the visible registry during a transient connection failure.
      });
    };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    const timer = window.setInterval(refresh, 5000);
    return () => {
      active = false; window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [bootstrap]);
  useEffect(() => {
    if (bootstrap) fit();
  }, [resultsCollapsed, resultsExpanded, bootstrap, fit]);
  useEffect(() => {
    if (!bootstrap || !documentsRef.current.length) return;
    const timer = setTimeout(async () => {
      try {
        if (agentBridge.current?.state) await agentBridge.current.flush();
        else await api.saveWorkspace(captureRef.current());
        if (graphRef.current === graph) setSaved(true);
      } catch {
        notify("未能保存草稿，请重试或导出 JSON 保存。");
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [graph, documents, activeId, bootstrap, panelWidths, notify]);
  useEffect(() => {
    const bridge = (
      window as Window & {
        chrome?: {
          webview?: {
            addEventListener: (
              event: string,
              callback: (event: MessageEvent) => void,
            ) => void;
            removeEventListener: (
              event: string,
              callback: (event: MessageEvent) => void,
            ) => void;
            postMessage: (value: unknown) => void;
          };
        };
      }
    ).chrome?.webview;
    if (!bootstrap?.desktop || !bridge) return;
    const closing = (event: MessageEvent) => {
      if (event.data?.type !== "prepare-close") return;
      void (agentBridge.current?.state ? agentBridge.current.flush() : api.saveWorkspace(captureRef.current())).then(
        () => bridge.postMessage({ type: "draft-saved" }),
        () => bridge.postMessage({ type: "draft-save-failed" }),
      );
    };
    bridge.addEventListener("message", closing);
    bridge.postMessage({ type: "studio-ready" });
    return () => bridge.removeEventListener("message", closing);
  }, [bootstrap]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(
      () => setToast(null),
      toast.type === "error" ? 9000 : 3500,
    );
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!job?.id) return;
    setEvents([]);
    const source = new EventSource(api.url(`/api/jobs/${job.id}/events`));
    let warned = false;
    source.addEventListener("update", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as {
        job: Job;
        events: RunEvent[];
        done: boolean;
      };
      setJob((previous) => ({ ...payload.job, graph: previous?.graph }));
      const memoryStart = payload.events.find(event => event.event === "run_started" && typeof event.available_at_start_bytes === "number");
      if (memoryStart && typeof memoryStart.budget_bytes === "number") {
        const budget = memoryStart.budget_bytes;
        setBootstrap(previous => previous ? {...previous, automatic_memory_budget_bytes: budget} : previous);
      }
      warned = false;
      setEvents((previous) => {
        const keys = new Set(previous.map((e) => JSON.stringify(e)));
        return [
          ...previous,
          ...payload.events.filter((e) => !keys.has(JSON.stringify(e))),
        ].slice(-5000);
      });
      if (payload.done) {
        source.close();
        setResultsExpanded(true);
        setResultsCollapsed(false);
        void api
          .history()
          .then(setHistory)
          .catch((e) => notify(e.message));
      }
    });
    source.onerror = () => {
      if (!warned) {
        warned = true;
        notify("事件连接中断，正在自动重连。任务仍在本地进程中运行。");
      }
    };
    return () => source.close();
  }, [job?.id, notify]);

  let order: string[] = [];
  try {
    order = executionOrder(graph).filter(
      (id) => graph.nodes.find((n) => n.id === id)?.kind !== "source",
    );
  } catch {
    /* compiler supplies a located error on Check */
  }
  const stale = useMemo(
    () => !!job?.graph && runSignature(graph) !== runSignature(job.graph),
    [graph, job?.graph],
  );
  const statuses = useMemo(() => {
    const result: Record<string, string> = {};
    let current = -1;
    if (stale) return result;
    for (const event of events) {
      if (event.event === "step_plan") {
        current = Number(event.index) - 1;
        const id = job?.order?.[current];
        if (id) result[id] = "running";
      }
      if (event.event === "step_finished") {
        const id = job?.order?.[current];
        if (id) result[id] = "finished";
      }
    }
    if (job?.status === "complete")
      for (const id of job.order || []) result[id] = "finished";
    for (const owner of new Set(Object.values(job?.node_owners || {}))) {
      const steps = (job?.order || []).filter(id => job?.node_owners?.[id] === owner);
      if (steps.every(id => result[id] === "finished")) result[owner] = "finished";
      else if (steps.some(id => result[id])) result[owner] = "running";
    }
    return result;
  }, [events, job?.status, job?.order, job?.node_owners, stale]);
  const blocks: Block[] = graph.nodes.map((model) => ({
    id: model.id,
    type: "block",
    position: model.position,
    selected: selection.includes(model.id),
    ariaLabel: displayTitle(model, specFor(model, catalog)),
    width: NODE_LAYOUT.width,
    measured: nodeMeasurements[model.id],
    height:
      NODE_LAYOUT.bodyHeight +
      portRowHeight(inputCount(model, specFor(model, catalog))) +
      portRowHeight(outputCount(model, specFor(model, catalog))) +
      2,
    draggable: !busy,
    deletable: !busy,
    data: {
      model,
      spec: specFor(model, catalog),
      order: order.indexOf(model.id) + 1,
      status: statuses[model.id],
      invalid: invalid === model.id || contracts?.edges.some(edge => edge.target === model.id && edge.status === "incompatible"),
      contracts: contracts?.nodes[model.id],
      contractChecks: contracts?.edges.filter(edge => edge.target === model.id),
      busy: !!busy,
    },
  }));
  const edges = graph.edges.map((edge) => {
    const related = [edge.source, edge.target].some(
      (id) => selection.includes(id) || hoveredNode === id,
    );
    const finished = statuses[edge.source] === "finished";
    return {
      ...edge,
      type: "workflow",
      selected: selectedEdges.includes(edge.id),
      deletable: !busy,
      animated: busy && statuses[edge.target] === "running",
      className: `${related ? "is-related" : ""} ${finished ? "is-finished" : ""} ${contracts?.edges.some(check => check.id === edge.id && check.status === "incompatible") ? "is-contract-invalid" : ""}`,
      interactionWidth: 22,
    };
  });
  function deleteNodes(ids: string[]) {
    if (busy) return;
    commit((current) => ({
      ...current,
      nodes: current.nodes.filter((n) => !ids.includes(n.id)),
      edges: current.edges.filter(
        (e) => !ids.includes(e.source) && !ids.includes(e.target),
      ),
      memory: {
        ...current.memory,
        keep: (current.memory.keep || []).filter(
          (name) =>
            !current.nodes.some(
              (n) =>
                ids.includes(n.id) && retainedOutputs(n, specFor(n, catalog)).includes(name),
            ),
        ),
      },
    }));
    if (selected && ids.includes(selected)) setSelected(null);
    if (inspected && ids.includes(inspected)) closeInspector();
  }
  function nodeChanges(changes: NodeChange<Block>[]) {
    const dimensions = changes.filter((change) => change.type === "dimensions");
    if (dimensions.length)
      setNodeMeasurements((previous) => {
        const next = { ...previous };
        let changed = false;
        for (const change of dimensions) {
          if (!change.dimensions) continue;
          const before = previous[change.id];
          if (
            before?.width !== change.dimensions.width ||
            before?.height !== change.dimensions.height
          ) {
            next[change.id] = change.dimensions;
            changed = true;
          }
        }
        return changed ? next : previous;
      });
    const selects = changes.filter((c) => c.type === "select");
    if (selects.length)
      setSelection((current) => {
        const next = new Set(current);
        for (const change of selects) {
          if (change.selected) next.add(change.id);
          else next.delete(change.id);
        }
        return [...next];
      });
    if (busy) return;
    const removes = changes.filter((c) => c.type === "remove").map((c) => c.id);
    if (removes.length) {
      deleteNodes(removes);
      return;
    }
    const positions = changes.filter((c) => c.type === "position");
    if (positions.length)
      putGraph({
        ...graphRef.current,
        nodes: graphRef.current.nodes.map((node) => {
          const change = positions.find((c) => c.id === node.id);
          return change?.position
            ? { ...node, position: change.position }
            : node;
        }),
      });
  }
  function edgeChanges(changes: EdgeChange[]) {
    const selects = changes.filter((c) => c.type === "select");
    if (selects.length)
      setSelectedEdges((current) => {
        const next = new Set(current);
        for (const change of selects) {
          if (change.selected) next.add(change.id);
          else next.delete(change.id);
        }
        return [...next];
      });
    if (busy) return;
    const removes = changes.filter((c) => c.type === "remove").map((c) => c.id);
    if (removes.length)
      commit((current) => ({
        ...current,
        edges: current.edges.filter((e) => !removes.includes(e.id)),
      }));
  }
  async function connect(connection: Connection) {
    if (busy || connecting.current || !connection.source || !connection.target) return;
    const snapshot = graphRef.current;
    const targetHandle = connection.targetHandle || "in-0",
      sourceHandle = connection.sourceHandle || "out";
    if (
      snapshot.edges.some(
        (e) =>
          e.target === connection.target && e.targetHandle === targetHandle,
      )
    )
      return notify("这个输入端口已有连线。选中连线并按 Delete 删除后再连接。");
    if (wouldCycle(snapshot.edges, connection.source, connection.target))
      return notify("这条连线会形成环路，请按数据生成方向连接。");
    const edge: GraphEdge = {
      ...connection,
      sourceHandle,
      targetHandle,
      id: `edge-${crypto.randomUUID()}`,
    };
    connecting.current = true;
    try {
      const candidate = { ...snapshot, edges: [...snapshot.edges, edge] };
      const analysis = await api.contracts(candidate);
      if (contractSignature(graphRef.current) !== contractSignature(snapshot))
        return notify("工作流刚刚发生变化，请重新连接以检查最新契约。");
      const check = analysis.edges.find(item => item.id === edge.id);
      if (!check) throw new Error("没有收到端口兼容性结果，请重试。");
      if (check.status === "incompatible") {
        setInvalid(edge.target);
        return notify(`无法连接：${check.reasons.join("；")}`);
      }
      commit(current => ({ ...current, edges: [...current.edges, edge] }));
      setContractResult({ key: contractSignature(candidate), value: analysis });
      if (check.status === "unknown") notify("连线已建立；部分字段待读取后确认，悬停输入 info 查看。", "success");
    } catch (error) {
      notify(`无法完成连线检查：${(error as Error).message}`);
    } finally {
      connecting.current = false;
    }
  }
  function add(operator?: string, position?: { x: number; y: number }) {
    if (busy) return;
    if (operator && (libraryState.disabled.includes(operator) || libraryState.hidden.includes(operator))) return;
    const spec = catalog.operators.find((o) => o.name === operator);
    const area = canvas.current?.getBoundingClientRect();
    const location =
      position ||
      flow.screenToFlowPosition({
        x: (area?.left || 0) + (area?.width || 600) / 2 - 100,
        y: (area?.top || 0) + (area?.height || 400) / 2 - 60,
      });
    const route = routes.find(item => item.id === operator);
    if (operator && operator !== "source" && !spec && !route) return;
    const node = route ? makeRouteNode(graphRef.current, route, location) : makeNode(graphRef.current, spec, location);
    commit((current) => ({ ...current, nodes: [...current.nodes, node] }));
    setSelected(node.id);
    setSelection([node.id]);
  }
  function undo() {
    if (agentBridge.current?.state && !busy) {void agentBridge.current.undo(activeIdRef.current).catch(failure); return;}
    if (!past.length || busy) return;
    const previous = past[past.length - 1];
    const current = clone(graphRef.current);
    setPast(past.slice(0, -1));
    setFuture((items) => [current, ...items]);
    putGraph(previous);
  }
  function redo() {
    if (agentBridge.current?.state && !busy) {void agentBridge.current.undo(activeIdRef.current, true).catch(failure); return;}
    if (!future.length || busy) return;
    const current = clone(graphRef.current);
    setPast((items) => [...items, current]);
    putGraph(future[0]);
    setFuture(future.slice(1));
  }
  function updateNode(id: string, patch: Partial<GraphNode>) {
    commit((current) => {
      const original = current.nodes.find((n) => n.id === id)!;
      const nodes = current.nodes.map((n) =>
        n.id === id ? { ...n, ...patch } : n,
      );
      const updated = nodes.find((n) => n.id === id)!;
      const keep = (current.memory.keep || []).map((k) =>
        k === String(original.params.output || id)
          ? String(updated.params.output || id)
          : k,
      );
      const validPorts = inputCount(updated, specFor(updated, catalog));
      return {
        ...current,
        nodes,
        edges: current.edges.filter(
          (e) =>
            e.target !== id || Number(e.targetHandle.slice(3)) < validPorts,
        ),
        memory: { ...current.memory, keep },
      };
    });
  }
  function failure(error: unknown) {
    const value = error as ApiError;
    notify(value.message || "操作未完成。");
    setInvalid(value.nodeId);
    if (value.nodeId) {
      inspectNode(value.nodeId);
    }
  }
  async function validate() {
    setAction("validate");
    try {
      const result = await api.validate(graphRef.current);
      setInvalid(undefined);
      notify(
        `检查通过 · ${result.order.length} 个步骤，按固定顺序执行`,
        "success",
      );
    } catch (error) {
      failure(error);
    } finally {
      setAction("");
    }
  }
  async function run() {
    setAction("run");
    try {
      const current = await api.run(graphRef.current);
      setJob(current);
      setTab("results");
      setResultsCollapsed(false);
      setHistory(await api.history());
      setInvalid(undefined);
    } catch (error) {
      failure(error);
    } finally {
      setAction("");
    }
  }
  async function stop() {
    if (!job) return;
    setAction("stop");
    try {
      setJob(await api.cancel(job.id));
    } catch (error) {
      failure(error);
    } finally {
      setAction("");
    }
  }
  async function importFile(file?: File) {
    if (!file) return;
    setAction("import");
    try {
      const text = await file.text();
      const next = file.name.toLowerCase().endsWith(".json")
        ? normalizeGraph(JSON.parse(text))
        : autoLayout(normalizeGraph(await api.import(text, importBase)));
      openPages([{graph: next}]);
      setSelected(next.nodes[0]?.id || null);
      closeInspector();
      setJob(null);
      setEvents([]);
      fit();
      notify("已载入工作流，可检查后运行。", "success");
    } catch (error) {
      failure(error);
    } finally {
      setAction("");
      if (importInput.current) importInput.current.value = "";
    }
  }
  async function exportYaml() {
    setExportOpen(false);
    setAction("export");
    try {
      const value = await api.export(graphRef.current);
      downloadText("pipeline.yaml", value.yaml, "text/yaml");
    } catch (error) {
      failure(error);
    } finally {
      setAction("");
    }
  }
  async function save() {
    setSaveDialog(clone(graphRef.current));
  }
  useEffect(() => {
    const editable = (target: EventTarget | null) => target instanceof HTMLElement && !!target.closest('input, textarea, select, [contenteditable="true"], [role="dialog"]');
    function nativeCopy(event: ClipboardEvent) {
      if (editable(event.target) || !selection.length) return;
      const fragment = copyFragment(graphRef.current, selection);
      if (!fragment.nodes.length) return;
      event.preventDefault();
      event.clipboardData?.setData("text/plain", JSON.stringify(fragment));
      clipboard.current = fragment;
      if (event.type === "cut" && !busy) deleteNodes(selection);
    }
    function nativePaste(event: ClipboardEvent) {
      if (editable(event.target) || busy) return;
      const text = event.clipboardData?.getData("text/plain");
      if (!text?.includes('"biopipe/graph-fragment-v1"')) return;
      event.preventDefault();
      try {
        const fragment = parseFragment(text), value = pasteFragment(graphRef.current, fragment);
        clipboard.current = fragment; commit(value.graph); setSelection(value.ids); setSelected(value.ids[0] || null); setSelectedEdges([]);
      } catch(error) {failure(error);}
    }
    function keyboard(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (event.key === "Escape") {
        setContextMenu(null);
        setLibraryOpen(false);
        closeInspector();
        setExportOpen(false);
        return;
      }
      if (target.closest('input, textarea, select, [contenteditable="true"], [role="dialog"]'))
        return;
      if (event.ctrlKey || event.metaKey) {
        const key = event.key.toLowerCase();
        if (["a", "c", "v", "x", "d"].includes(key)) event.preventDefault();
        if (key === "a") {setSelection(graphRef.current.nodes.map(n=>n.id)); setSelectedEdges(graphRef.current.edges.map(e=>e.id));}
        if (key === "c") void copySelection();
        if (key === "x" && !busy) void copySelection(true);
        if (key === "v") void pasteSelection();
        if (key === "d") void pasteSelection(true);
        if (key === "t" && event.shiftKey) {event.preventDefault(); reopenPage();}
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        save();
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
        event.preventDefault();
        redo();
      }
      if (event.key === "Enter" && !event.ctrlKey && !event.metaKey) {
        const id = target.closest<HTMLElement>(".react-flow__node")?.dataset.id;
        if (id && !target.closest(".react-flow__handle")) {
          event.preventDefault();
          inspectNode(id);
        }
      }
      if (event.key === "/") {
        event.preventDefault();
        setLibraryOpen(true);
        requestAnimationFrame(() =>
          document
            .querySelector<HTMLInputElement>('input[aria-label="搜索算子"]')
            ?.focus(),
        );
      }
    }
    window.addEventListener("keydown", keyboard);
    window.addEventListener("copy", nativeCopy); window.addEventListener("cut", nativeCopy); window.addEventListener("paste", nativePaste);
    return () => {window.removeEventListener("keydown", keyboard); window.removeEventListener("copy", nativeCopy); window.removeEventListener("cut", nativeCopy); window.removeEventListener("paste", nativePaste);};
  }, [past, future, busy, selection, documents, activeId, inspectNode, closeInspector]);

  if (!bootstrap)
    return (
      <div className="boot-state" role="status" aria-live="polite">
        <div className="brand-mark">
          <Dna size={31} />
        </div>
        <h1>BioPipe Studio</h1>
        <p>{bootError || "正在连接本地工作台…"}</p>
        {bootError ? (
          <button className="primary-button" onClick={() => void load()}>
            重新连接
          </button>
        ) : (
          <LoadingSkeleton />
        )}
      </div>
    );
  const filtered = catalog.operators.filter((o) => (showHidden || !libraryState.hidden.includes(o.name)) &&
    `${o.title} ${o.name} ${o.description} ${(o.title_aliases || []).join(" ")}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const categories = [...new Set(filtered.map((o) => o.category))].sort(
    (a, b) =>
      ["质量控制", "统计分析", "数据整理", "可视化", "扩展算子"].indexOf(a) -
      ["质量控制", "统计分析", "数据整理", "可视化", "扩展算子"].indexOf(b),
  );
  return (
    <div
      className={`studio-shell ${resultsExpanded ? "results-expanded" : ""} ${resultsCollapsed ? "results-collapsed" : ""} ${resizingPanel ? "is-resizing-panel" : ""}`}
      style={{ "--library-width": `${displayedPanels.library}px`, "--inspector-width": `${displayedPanels.inspector}px` } as CSSProperties}
    >
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <Dna size={21} weight="regular" />
          </div>
          <div>
            <strong>
              BioPipe<span>Studio</span>
            </strong>
          </div>
        </div>
        <DocumentTabs documents={documents} active={activeId} saved={saved} onSelect={switchPage} onClose={closePage} onNew={newPage} onRename={name => commit(current => ({...current, name}))}/>
        <div className="topbar-actions">
          <button
            className="icon-button save-control"
            aria-label="保存路线"
            title="保存路线与注册接口 Ctrl+S"
            onClick={save}
          >
            <FloppyDisk size={18} />
          </button>
          <AppearanceMenu />
          <div className="file-menu">
            <button
              className="subtle-button"
              aria-expanded={exportOpen}
              onClick={() => setExportOpen(!exportOpen)}
            >
              <ArrowDown size={16} />
              <span>文件</span>
              <CaretDown size={11} />
            </button>
            {exportOpen && (
              <>
                <button
                  className="menu-scrim"
                  aria-label="关闭文件菜单"
                  onClick={() => setExportOpen(false)}
                />
                <div className="dropdown">
                  <button onClick={() => {setExportOpen(false); setPicker("open");}}><FolderOpen size={16}/>打开已保存画布</button>
                  <button onClick={() => {setExportOpen(false); void save();}}><FloppyDisk size={16}/>保存路线与接口</button>
                  <button
                    disabled={busy}
                    onClick={() => {
                      setExportOpen(false);
                      importInput.current?.click();
                    }}
                  >
                    <ArrowUp size={16} />
                    导入 YAML / JSON
                  </button>
                  <label className="menu-base">
                    <span>YAML 输入相对目录</span>
                    <input
                      value={importBase}
                      placeholder="例如 tasks/demo"
                      onChange={(e) => setImportBase(e.target.value)}
                    />
                  </label>
                  <button
                    onClick={() => {
                      void api.prepareWorkflow(graphRef.current).then(value => downloadText(`${value.name.replace(/[\\/:*?"<>|]/g, "_")}.biopipe.json`, JSON.stringify(value, null, 2))).catch(failure);
                      setExportOpen(false);
                    }}
                  >
                    <ArrowDown size={16} />
                    导出工作流 JSON
                  </button>
                  <button onClick={() => void exportYaml()}>
                    <ArrowDown size={16} />
                    导出执行 YAML
                  </button>
                  <div className="menu-line" />
                  <button
                    disabled={busy}
                    onClick={() => {
                      openPages([{graph: normalizeGraph(bootstrap.demo)}]);
                      setSelected("pca");
                      closeInspector();
                      setExportOpen(false);
                      fit();
                    }}
                  >
                    <ArrowCounterClockwise size={16} />
                    载入分支示例
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => {
                      newPage();
                      setExportOpen(false);
                    }}
                  >
                    <Plus size={16} />
                    新建空白工作流
                  </button>
                  <button disabled={!closedDocuments.current.length} onClick={() => {setExportOpen(false); reopenPage();}}><ArrowCounterClockwise size={16}/>恢复关闭的页面 <kbd>Ctrl⇧T</kbd></button>
                </div>
              </>
            )}
          </div>
          <span className="toolbar-divider" />
          <button className="subtle-button agent-control" title="连接自己的 Agent · CLI / MCP" onClick={() => setAgentPanel(true)}>
            <span className={agentReady ? "agent-dot ready" : "agent-dot"}/>Agent
          </button>
          <button
            className="subtle-button check-control"
            disabled={busy || !!action}
            onClick={() => void validate()}
          >
            <CheckCircle size={17} />
            检查
          </button>
          {busy ? (
            <button
              className="stop-button"
              disabled={!!action}
              onClick={() => void stop()}
            >
              <Stop size={14} weight="fill" />
              停止运行
            </button>
          ) : (
            <button
              className="primary-button"
              disabled={!!action}
              onClick={() => void run()}
            >
              {action === "run" ? (
                <CircleNotch size={16} className="spin" />
              ) : (
                <Lightning size={16} weight="fill" />
              )}
              运行
            </button>
          )}
        </div>
        <input
          ref={importInput}
          type="file"
          accept=".json,.yaml,.yml"
          className="sr-only"
          aria-label="导入工作流文件"
          onChange={(e) => void importFile(e.target.files?.[0])}
        />
        <input ref={routeImport} type="file" multiple accept=".json" className="sr-only" aria-label="导入路线 JSON" onChange={e => void importRoutes(e.target.files)}/>
      </header>
      <div className="workspace">
        {(libraryOpen || inspectorOpen) && (
          <button
            className="drawer-scrim"
            aria-label="关闭工具面板"
            onClick={() => {
              setLibraryOpen(false);
              setInspectorOpen(false);
            }}
          />
        )}
        <aside
          className={`library panel ${libraryOpen ? "drawer-open" : ""}`}
          aria-label="算子库"
        >
          <div className="panel-heading">
            <h2>算子库</h2>
            <span className="count-badge">{catalog.operators.filter(item => !libraryState.hidden.includes(item.name)).length + routes.length}</span>
            <button className="icon-button register-route-button" aria-label="添加路线算子" title="从已保存路线添加算子" onClick={() => setPicker("register")}><Plus size={18}/></button>
            <button
              className="icon-button mobile-close"
              aria-label="关闭算子库"
              onClick={() => setLibraryOpen(false)}
            >
              <X size={16} />
            </button>
          </div>
          <label className="search-field">
            <MagnifyingGlass size={16} />
            <input
              aria-label="搜索算子"
              placeholder="搜索算子"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <kbd>/</kbd>
          </label>
          {!!libraryState.hidden.length && <button className={`library-removed-toggle ${showHidden ? "is-active" : ""}`} aria-pressed={showHidden} onClick={() => setShowHidden(value => !value)}><Trash size={13}/>{showHidden ? "收起已删除" : "已删除"}<span>{libraryState.hidden.length}</span></button>}
          <button
            className="source-add"
            disabled={busy}
            draggable={!busy}
            onDragStart={(e) => {
              e.dataTransfer.setData("application/biopipe", "source");
              e.dataTransfer.effectAllowed = "move";
            }}
            onClick={() => add()}
          >
            <OperatorIcon name="Database" size={18} />
            <span>
              <strong>输入数据</strong>
            </span>
            <Plus size={15} />
          </button>
          <div className="library-scroll">
            {(!search || routes.some(route => route.name.toLowerCase().includes(search.toLowerCase()))) && <LibrarySection name="路线算子" count={routes.filter(route => route.name.toLowerCase().includes(search.toLowerCase())).length} sectionKey="routes" search={search} className="route-library">
              {!routes.length && <button className="route-empty" onClick={() => setPicker("register")}>
                <Stack size={20}/><strong>添加已保存路线</strong><Plus size={14}/>
              </button>}
              {routes.filter(route => route.name.toLowerCase().includes(search.toLowerCase())).map(route => <button key={route.id} className={`operator-item route-item ${libraryState.disabled.includes(route.id) ? "is-library-disabled" : ""}`} title={`${routeSpec(route).description} · 右键管理`} disabled={busy} aria-disabled={libraryState.disabled.includes(route.id)} draggable={!busy && !libraryState.disabled.includes(route.id)}
                onClick={() => add(route.id)} onContextMenu={event => {event.preventDefault(); setContextMenu({x: event.clientX, y: event.clientY, route, libraryKey: route.id});}}
                onDragStart={event => {event.dataTransfer.setData("application/biopipe", route.id); event.dataTransfer.effectAllowed = "move";}}>
                <span className="operator-icon"><Stack size={18}/></span><span><strong>{route.name}</strong><small>{libraryState.disabled.includes(route.id) ? "已禁用 · " : ""}{route.graph.interface?.inputs.length} → {route.graph.interface?.outputs.length} · v{route.version}</small></span><Plus className="add-hint" size={14}/>
              </button>)}
            </LibrarySection>}
            {categories.map((category) => (
              <LibrarySection key={category} name={category} count={filtered.filter(o => o.category === category).length} sectionKey={`operator:${category}`} search={search}>
                {filtered
                  .filter((o) => o.category === category)
                  .map((spec) => (
                    <button
                      key={spec.name}
                      className={`operator-item ${spec.preview ? "has-preview" : ""} ${libraryState.disabled.includes(spec.name) || libraryState.hidden.includes(spec.name) ? "is-library-disabled" : ""}`}
                      disabled={busy}
                      aria-disabled={libraryState.disabled.includes(spec.name) || libraryState.hidden.includes(spec.name)}
                      title={spec.description}
                      draggable={!busy && !libraryState.disabled.includes(spec.name) && !libraryState.hidden.includes(spec.name)}
                      onContextMenu={event => {event.preventDefault(); setContextMenu({x: event.clientX, y: event.clientY, libraryKey: spec.name});}}
                      onDragStart={(e) => {
                        e.dataTransfer.setData(
                          "application/biopipe",
                          spec.name,
                        );
                        e.dataTransfer.effectAllowed = "move";
                      }}
                      onClick={() => add(spec.name)}
                    >
                      <span className="operator-icon">
                        <OperatorArtwork spec={spec} size={18}/>
                      </span>
                      <span>
                        <strong>{spec.title}</strong>
                        {libraryState.hidden.includes(spec.name) ? <small>已删除</small> : libraryState.disabled.includes(spec.name) ? <small>已禁用</small> : null}
                      </span>
                      <Plus className="add-hint" size={14} />
                    </button>
                  ))}
              </LibrarySection>
            ))}
            {!filtered.length && !routes.some(r => r.name.toLowerCase().includes(search.toLowerCase())) && (
              <div className="search-empty">
                没有找到算子
                <br />
                <button className="text-button" onClick={() => setSearch("")}>
                  清空搜索
                </button>
              </div>
            )}
          </div>
          <div className="library-footer">
            <button className="library-packages" onClick={() => setPluginsOpen(true)}><Package size={16}/>算子包管理</button>
          </div>
          <PanelResizeHandle side="library" width={displayedPanels.library} min={panelLimits.library.min}
            max={panelMaximum("library", displayedPanels, windowWidth)} onResize={value => resizePanel("library", value)}
            onReset={() => resizePanel("library", null)} onResizing={setResizingPanel}/>
        </aside>
        <div className="canvas-column">
          <main className="canvas-area" id="workflow-canvas" role="tabpanel" aria-label={graph.name} ref={canvas}>
            <div className="canvas-header">
              <div className="canvas-topline">
                <div>
                  <h1>{graph.name}</h1>
                  {documents.find(doc=>doc.id===activeId)?.workflow_id && <span className="canvas-route-label"><Stack size={11}/>路线图 · v{documents.find(doc=>doc.id===activeId)?.workflow_version}</span>}
                </div>
                <div className="canvas-meta">
                  <span>{graph.nodes.length} 个节点</span>
                  <span className="meta-dot" />
                  <span>{graph.edges.length} 条连接</span>
                </div>
              </div>
              <div className="canvas-toolbar">
                <div className="toolbar-group">
                  <button
                    className="icon-button show-library"
                    aria-label="打开算子库"
                    onClick={() => {
                      setLibraryOpen(true);
                      setInspectorOpen(false);
                    }}
                  >
                    <List size={18} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label="撤销"
                    title="撤销 Ctrl+Z"
                    disabled={!past.length || busy}
                    onClick={undo}
                  >
                    <ArrowCounterClockwise size={17} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label="重做"
                    title="重做 Ctrl+Shift+Z"
                    disabled={!future.length || busy}
                    onClick={redo}
                  >
                    <ArrowClockwise size={17} />
                  </button>
                  <span className="toolbar-divider" />
                  <button
                    className="text-button"
                    title="自动排布并适配画布"
                    disabled={busy || !graph.nodes.length}
                    onClick={() => {
                      try {
                        commit(autoLayout(graphRef.current));
                        fit();
                      } catch (error) {
                        failure(error);
                      }
                    }}
                  >
                    <Rows size={16} />
                    <span>自动排布</span>
                  </button>
                </div>
                <div className="toolbar-group">
                  <button
                    className="icon-button show-inspector"
                    aria-label="打开检查器"
                    onClick={() => {
                      inspectNode(selected);
                    }}
                  >
                    <SidebarSimple size={17} />
                  </button>
                  <button
                    className={`text-button ${settings ? "active" : ""}`}
                    aria-label="执行设置"
                    onClick={() => {
                      setSettings(!settings);
                      setInspectorOpen(true);
                      setLibraryOpen(false);
                    }}
                  >
                    <GearSix size={16} />
                    <span>执行设置</span>
                  </button>
                </div>
              </div>
            </div>
            <ReactFlow<Block>
              nodes={blocks}
              edges={edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onNodesChange={nodeChanges}
              onEdgesChange={edgeChanges}
              onConnect={connect}
              onNodeMouseEnter={(_, node) => setHoveredNode(node.id)}
              onNodeMouseLeave={() => setHoveredNode(null)}
              onNodeContextMenu={(event, node) => {event.preventDefault(); if(!selection.includes(node.id)) {setSelection([node.id]); setSelected(node.id);} setContextMenu({x: event.clientX, y: event.clientY, route: node.data.model.route || undefined, nodeId: node.id});}}
              onPaneContextMenu={event => {event.preventDefault(); setContextMenu({x: event.clientX, y: event.clientY});}}
              onNodeClick={(_, node) => {
                setSelected(node.id);
              }}
              onNodeDoubleClick={(event, node) => {
                if (
                  (event.target as HTMLElement).closest(".react-flow__handle")
                )
                  return;
                inspectNode(node.id);
              }}
              onPaneClick={() => {
                setContextMenu(null);
                setSelected(null);
                setSelection([]);
                setSelectedEdges([]);
                closeInspector();
              }}
              onMoveEnd={() => {const next = captureWorkspace().documents; documentsRef.current = next; setDocuments(next);}}
              onNodeDragStart={() => {
                dragOrigin.current = clone(graphRef.current);
              }}
              onNodeDragStop={() => {
                if (
                  dragOrigin.current &&
                  JSON.stringify(dragOrigin.current) !==
                    JSON.stringify(graphRef.current)
                ) {
                  const origin = dragOrigin.current;
                  setPast((items) => [...items.slice(-29), origin!]);
                  setFuture([]);
                }
                dragOrigin.current = null;
              }}
              onDragOver={(event) => {
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
              }}
              onDrop={(event) => {
                event.preventDefault();
                const type = event.dataTransfer.getData("application/biopipe");
                if (type)
                  add(
                    type === "source" ? undefined : type,
                    flow.screenToFlowPosition({
                      x: event.clientX,
                      y: event.clientY,
                    }),
                  );
              }}
              minZoom={0.2}
              maxZoom={1.6}
              zoomOnDoubleClick={false}
              onlyRenderVisibleElements
              nodesConnectable={!busy}
              connectionLineStyle={{ stroke: "var(--accent)", strokeWidth: 2 }}
              deleteKeyCode={["Backspace", "Delete"]}
              selectionMode={SelectionMode.Partial}
              selectionKeyCode="Shift"
              multiSelectionKeyCode={["Shift", "Control", "Meta"]}
              panOnDrag={[0, 1]}
              panActivationKeyCode="Space"
              proOptions={{ hideAttribution: true }}
              ariaLabelConfig={{
                "node.a11yDescription.default":
                  "单击选中，双击或 Enter 查看参数，方向键移动，Delete 删除。",
                "edge.a11yDescription.default": "按 Delete 删除连接。",
              }}
            >
              <Background
                id="biopipe-grid-fine"
                bgColor="transparent"
                variant={BackgroundVariant.Lines}
                gap={24}
                lineWidth={0.5}
                color="var(--grid-fine)"
              />
              <Background
                id="biopipe-grid-major"
                bgColor="transparent"
                variant={BackgroundVariant.Lines}
                gap={120}
                lineWidth={0.65}
                color="var(--grid-major)"
              />
            </ReactFlow>
            {!graph.nodes.length && (
              <div className="canvas-empty">
                <div className="empty-workflow" aria-hidden="true">
                  <span className="empty-workflow-source"><OperatorIcon name="Database" size={24}/></span>
                  <svg viewBox="0 0 86 96"><path d="M0 48H22C44 48 40 18 62 18H86M22 48C44 48 40 78 62 78H86"/></svg>
                  <span className="empty-workflow-target"><SquaresFour size={20}/></span>
                  <span className="empty-workflow-target"><Rows size={20}/></span>
                </div>
                <button className="primary-button canvas-empty-action" onClick={() => add()}>
                  <Plus size={16} aria-hidden="true" />
                  <span>添加输入数据</span>
                </button>
              </div>
            )}
            <div className="canvas-bottomline">
              <HelpTip label="画布快捷键" icon={<Keyboard size={18}/>} above>
                <span className="shortcut-row"><span>框选</span><kbd>Shift + 拖动</kbd></span>
                <span className="shortcut-row"><span>多选</span><kbd>Ctrl + 单击</kbd></span>
                <span className="shortcut-row"><span>平移</span><kbd>中键拖动</kbd></span>
                <span className="shortcut-row"><span>复制 / 粘贴</span><kbd>Ctrl + C / V</kbd></span>
                <span className="shortcut-row"><span>查看参数</span><kbd>双击 / Enter</kbd></span>
              </HelpTip>
              <div className="zoom-controls">
                <button
                  className="icon-button"
                  aria-label="缩小画布"
                  onClick={() =>
                    void flow.zoomOut({
                      duration: window.matchMedia(
                        "(prefers-reduced-motion: reduce)",
                      ).matches
                        ? 0
                        : 150,
                    })
                  }
                >
                  <Minus size={16} />
                </button>
                <button
                  className="icon-button"
                  aria-label="放大画布"
                  onClick={() =>
                    void flow.zoomIn({
                      duration: window.matchMedia(
                        "(prefers-reduced-motion: reduce)",
                      ).matches
                        ? 0
                        : 150,
                    })
                  }
                >
                  <Plus size={16} />
                </button>
                <span className="toolbar-divider" />
                <button
                  className="icon-button"
                  aria-label="适配画布"
                  title="适配画布"
                  onClick={fit}
                >
                  <ArrowsOut size={17} />
                </button>
              </div>
            </div>
          </main>
          <Results
            job={job}
            events={events}
            history={history}
            tab={tab}
            onTab={(value) => {
              setTab(value);
              setResultsExpanded(true);
              setResultsCollapsed(false);
            }}
            onError={notify}
            stale={stale}
            collapsed={resultsCollapsed}
            onToggle={() => {
              setResultsCollapsed(!resultsCollapsed);
              setResultsExpanded(true);
              requestAnimationFrame(fit);
            }}
            onJob={(id) => {
              void api.job(id).then(setJob).catch(failure);
            }}
            onRestore={(value) => {
              if (!value.graph || busy) return;
              openPages([{graph: normalizeGraph(value.graph)}]);
              setJob(value);
              setSelected(null);
              closeInspector();
              fit();
              notify("已载入这次运行的画布与参数。", "success");
            }}
          />
        </div>
        <div className={`inspector-wrap ${inspectorOpen ? "drawer-open" : ""}`}>
          <PanelResizeHandle side="inspector" width={displayedPanels.inspector} min={panelLimits.inspector.min}
            max={panelMaximum("inspector", displayedPanels, windowWidth)} onResize={value => resizePanel("inspector", value)}
            onReset={() => resizePanel("inspector", null)} onResizing={setResizingPanel}/>
          <Inspector
            graph={graph}
            catalog={catalog}
            nodeId={inspected}
            settings={settings}
            busy={!!busy}
            uploadLimit={bootstrap.upload_limit_mb}
            automaticMemoryFraction={bootstrap.automatic_memory_fraction}
            automaticMemoryBudget={bootstrap.automatic_memory_budget_bytes}
            onNode={updateNode}
            onMemory={(memory) => commit((current) => ({ ...current, memory }))}
            onParams={(params) => commit((current) => ({...current, params}))}
            onDelete={(id) => deleteNodes([id])}
            onError={notify}
            onClose={closeInspector}
            onOpenRoute={openRoute}
          />
        </div>
      </div>
      <footer className="statusbar">
        <span>
          <span className="status-dot complete" />
          {saved ? "已保存" : "保存中…"}
        </span>
        <span className="execution-caption">
          {job ? statusLabel[job.status] : "就绪"}
          <span className="meta-dot" />
          {order.length} 个算子
        </span>
        <span>
          BioPipe Studio <span className="mono">0.3</span>
        </span>
      </footer>
      {contextMenu && <>
        <div className="context-dismiss" onMouseDown={() => setContextMenu(null)} onContextMenu={e => {e.preventDefault(); setContextMenu(null);}}/>
        <div className="canvas-context" role="menu" aria-label={contextMenu.libraryKey ? "算子库操作" : "画布操作"} style={{left: Math.max(8, Math.min(contextMenu.x, window.innerWidth-244)), top: Math.max(8, Math.min(contextMenu.y, window.innerHeight-290))}}>
          {contextMenu.route && <><button role="menuitem" onClick={() => {openRoute(contextMenu.route!); setContextMenu(null);}}><Stack size={16}/>打开路线的算子图</button><div className="context-caption">{contextMenu.route.name} · v{contextMenu.route.version}</div><div className="menu-line"/></>}
          {contextMenu.libraryKey ? <>
            {libraryState.hidden.includes(contextMenu.libraryKey) ? <button role="menuitem" onClick={() => void manageLibrary(contextMenu.libraryKey!, "restore")}><ArrowCounterClockwise size={16}/>恢复到算子库</button> : <>
              <button role="menuitem" disabled={busy || libraryState.disabled.includes(contextMenu.libraryKey)} onClick={() => {add(contextMenu.libraryKey); setContextMenu(null);}}><Plus size={16}/>添加到画布</button>
              <button role="menuitem" onClick={() => void manageLibrary(contextMenu.libraryKey!, libraryState.disabled.includes(contextMenu.libraryKey!) ? "enable" : "disable")}>{libraryState.disabled.includes(contextMenu.libraryKey) ? <PlayCircle size={16}/> : <PauseCircle size={16}/>} {libraryState.disabled.includes(contextMenu.libraryKey) ? "启用算子" : "禁用算子"}</button>
              <div className="menu-line"/>
              <button role="menuitem" className="menu-danger" onClick={() => void manageLibrary(contextMenu.libraryKey!, "delete")}><Trash size={16}/>从算子库删除</button>
            </>}
          </> : <>
            <button role="menuitem" disabled={!selection.length && !selectedEdges.length} onClick={() => void copyAgentContext()}><Copy size={16}/>复制选区上下文</button>
            <div className="menu-line"/>
            <button role="menuitem" disabled={!selection.length} onClick={() => void copySelection()}><Copy size={16}/>复制节点 <kbd>Ctrl C</kbd></button>
            <button role="menuitem" disabled={busy} onClick={() => void pasteSelection(false, flow.screenToFlowPosition({x: contextMenu.x, y: contextMenu.y}))}><Clipboard size={16}/>粘贴 <kbd>Ctrl V</kbd></button>
            <button role="menuitem" disabled={!selection.length || busy} onClick={() => void pasteSelection(true)}><SquaresFour size={16}/>复制副本 <kbd>Ctrl D</kbd></button>
          </>}
        </div>
      </>}
      {pluginsOpen && <PluginPanel onClose={() => setPluginsOpen(false)} onChanged={async () => {const latest = await api.catalog(); setBootstrap(current => current ? {...current, catalog: latest} : current);}}/>}
      {picker && <WorkflowPicker mode={picker} onClose={() => setPicker(null)} onOpen={openSaved} onRegister={refreshRoutes} onImport={() => routeImport.current?.click()}/>}
      {saveDialog && <SaveWorkflowDialog graph={saveDialog} catalog={catalog} workflowId={documents.find(doc=>doc.id===activeId)?.workflow_id} version={documents.find(doc=>doc.id===activeId)?.workflow_version} onClose={() => setSaveDialog(null)} onSaved={savedWorkflow}/>}
      {agentPanel && <AgentPanel sessionId={agentBridge.current?.state?.id} command={bootstrap.agent_config} onClose={() => setAgentPanel(false)} onCopySelection={() => void copyAgentContext()}/>}
      {toast && (
        <div
          className={`toast ${toast.type}`}
          role={toast.type === "error" ? "alert" : "status"}
        >
          {toast.type === "success" ? <CheckCircle size={18} /> : <InfoIcon />}
          <span>{toast.message}</span>
          <button aria-label="关闭提示" onClick={() => setToast(null)}>
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
function InfoIcon() {
  return <span className="toast-error-mark">!</span>;
}
export default function App() {
  return (
    <ErrorBoundary>
      <ReactFlowProvider>
        <Studio />
      </ReactFlowProvider>
    </ErrorBoundary>
  );
}
