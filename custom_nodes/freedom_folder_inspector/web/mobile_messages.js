// web/mobile_messages.js
//
// The phone add-on (comfyui-mobile-frontend, mobile_latent_shape.py) sends a
// "mobile_latent_shape" message during every run, to whichever window queued
// it, so the PHONE can tell a batch of pictures from a video. When the desktop
// page queues the run, the message arrives here too - and ComfyUI's desktop page
// logs "Unknown message type mobile_latent_shape" for any message type nobody
// has registered (frontend 1.53.6, api.js: registered types are dispatched,
// unregistered ones are reported once with console.error).
//
// The desktop draws its own previews and has no use for the shape, so it
// registers the type and deliberately does nothing with it. The phone is
// unaffected: it still receives and uses the message exactly as before.
// Checked 2026-09-24: the add-on's latest upstream copy of mobile_latent_shape.py
// is identical to the installed one, so no newer version changes this.
import { api } from "../../scripts/api.js";

api.addEventListener("mobile_latent_shape", () => {
    // Meant for the phone. Nothing to do on the desktop.
});
