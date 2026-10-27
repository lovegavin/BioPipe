import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Results } from "./Results";
import type { Job, RunEvent } from "./types";

const job: Job = {id: "test-run", name: "Test", status: "failed", created_at: "2026-10-14T00:00:00Z", error: "startup sentinel"};
const render = (events: RunEvent[], consoleText = "", currentJob: Job = job) => renderToStaticMarkup(
  <Results job={currentJob} events={events} consoleText={consoleText} history={[]} tab="logs"
    onTab={() => {}} onJob={() => {}} onRestore={() => {}} onError={() => {}} collapsed={false}
    onToggle={() => {}} stale={false}/>,
);

describe("run log panel", () => {
  it("shows the persisted job error even when structured events are missing", () => {
    const html = render([]);
    expect(html).toContain("startup sentinel");
    expect(html).not.toContain("暂无运行日志");
  });
  it("renders operator messages and raw process output as text", () => {
    const html = render([{event: "operator_log", time: job.created_at, message: "operator sentinel <script>"}], "Traceback: console sentinel");
    expect(html).toContain("operator sentinel &lt;script&gt;");
    expect(html).toContain("Traceback: console sentinel");
    expect(html).toContain("完整进程日志");
  });
});

describe('historical results', () => {
  const report = {artifacts: [{artifact_id:'pcs',name:'PCA',disk_uri:'/server/cache/pcs',shape:[10,2],dtype:'float64',ram_estimate_bytes:160,storage:'disk'}],
    budget_bytes:1024,managed_peak_bytes:160,sampled_rss_peak_bytes:2048,plans:[]};
  const renderResult = (currentJob: Job) => renderToStaticMarkup(<Results job={currentJob} events={[]} history={[]} tab="results"
    onTab={()=>{}} onJob={()=>{}} onRestore={()=>{}} onError={()=>{}} collapsed={false} onToggle={()=>{}} stale={false}/>);
  it('offers the normal artifact and report viewer for server history', () => {
    const html=renderResult({...job,status:'complete',error:null,report,summary:{steps:[{name:'pca',export_path:'steps/01.json'}]},
      remote:{profile_id:'server',job_id:'test-run',name:'Compute server',workspace:'/server/work'}});
    expect(html).toContain('数据产物');expect(html).toContain('步骤报告');expect(html).toContain('Compute server');
    expect(html).not.toContain('remote-result-file');
  });
  it('retains partial results and a log entry for a failed run', () => {
    const html=renderResult({...job,report});
    expect(html).toContain('startup sentinel');expect(html).toContain('数据产物');expect(html).toContain('查看日志');
  });
  it('exposes saved figure links in the sidebar while leaving the data preview separate', () => {
    const html = renderResult({...job,status:'complete',error:null,report,summary:{steps:[{name:'scatter',export_path:'steps/01.json',
      figures:['png','pdf','svg'].map(format=>({format,path:`/server/figure.${format}`,filename:`figure.${format}`}))}]}});
    expect(html).toContain('输出图表');expect(html).toContain('打开 PDF');expect(html).toContain('打开 SVG');
    expect(html).toContain('/exports/0/figure?format=pdf');expect(html).toContain('数据产物');
  });
});
