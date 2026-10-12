import { createRoot } from "react-dom/client";
import "@fontsource-variable/geist";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(<App />);
