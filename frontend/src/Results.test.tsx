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
