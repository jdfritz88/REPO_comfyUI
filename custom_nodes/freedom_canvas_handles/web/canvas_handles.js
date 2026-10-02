// web/canvas_handles.js
//
// Easier-to-grab resize handles (user, 2026-10-01, choice 2: about twice as big,
// always faintly showing). Read from ComfyUI frontend 1.53.6 before writing this:
//
//   Boxes (nodes): four grab squares, one per corner - elements with a
//     "data-corner" of SE / NE / SW / NW (GraphView-*.js). Theirs are 20 x 20
//     (class h-5 w-5), 4 past the corner, and invisible until the mouse is over
//     the box. Ours: 40 x 40, centred on the corner (half inside, half outside,
//     so less of the box's own buttons and wire dots is covered), and always
//     faintly showing; full strength while the mouse is over the box.
//
//   Frames (node groups): resized only from the bottom-right corner, by a
//     triangle LGraphGroup.resizeLength long (10). ComfyUI draws that same
//     triangle with the same number, so raising it to 25 also makes the mark
//     you see bigger. The frame's triangle is always drawn, so it already shows.
//
//   The older canvas-drawn boxes (not used here, kept in step) use
//     LGraphNode.resizeHandleSize (15); raised to 30.
//
// Nothing in ComfyUI's own files is changed. If a ComfyUI update renames these,
// the page simply keeps ComfyUI's own sizes and the console says so.
import { app } from "../../scripts/app.js";

const NODE_CORNER = 40;      // was 20
const GROUP_CORNER = 25;     // was 10
const CANVAS_NODE_CORNER = 30;   // was 15

const CSS = `
[data-node-id] [data-corner]{width:${NODE_CORNER}px !important;height:${NODE_CORNER}px !important;
  opacity:.35 !important}
[data-node-id]:hover [data-corner],[data-node-id] [data-corner]:hover{opacity:1 !important}
[data-node-id] [data-corner="SE"]{right:-${NODE_CORNER / 2}px !important;bottom:-${NODE_CORNER / 2}px !important}
[data-node-id] [data-corner="NE"]{right:-${NODE_CORNER / 2}px !important;top:-${NODE_CORNER / 2}px !important}
[data-node-id] [data-corner="SW"]{left:-${NODE_CORNER / 2}px !important;bottom:-${NODE_CORNER / 2}px !important}
[data-node-id] [data-corner="NW"]{left:-${NODE_CORNER / 2}px !important;top:-${NODE_CORNER / 2}px !important}
`;

app.registerExtension({
  name: "freedom.canvas_handles",
  async setup() {
    if (!document.getElementById("freedom-canvas-handles-css")) {
      const s = document.createElement("style");
      s.id = "freedom-canvas-handles-css";
      s.textContent = CSS;
      document.head.append(s);
    }
    const G = window.LGraphGroup, N = window.LGraphNode;
    if (G && typeof G.resizeLength === "number") G.resizeLength = GROUP_CORNER;
    else console.warn("[Freedom canvas handles] frame corner size not found - ComfyUI's own size kept");
    if (N && typeof N.resizeHandleSize === "number") N.resizeHandleSize = CANVAS_NODE_CORNER;
    app.graph?.setDirtyCanvas?.(true, true);
  },
});
