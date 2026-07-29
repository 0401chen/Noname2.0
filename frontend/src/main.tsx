import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import { installBranding } from "./branding";
import "./styles.css";
import "./reviewer.css";
import "./demo.css";

installBranding();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
