"""
Stop-aware OneTrainer entry point.

Mirrors OneTrainer/scripts/train.py, with one addition: a watcher thread polls
a STOP file (path in the OT_STOP_FILE env var). When it appears, it calls
commands.stop(), which OneTrainer's trainer checks between steps and epochs and
returns cleanly - and then we always call trainer.end(), so the LoRA trained so
far is saved to output_model_destination.

Run with cwd = the OneTrainer directory, same args as train.py
(--config-path, optional --preset-path, --config-value ...).
"""

import json
import os
import sys
import threading
import time

_OT = os.environ.get("ONETRAINER_DIR",
                     r"F:\Apps\freedom_system\app_cabinet\OneTrainer")
for p in (_OT, os.path.join(_OT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from util.import_util import script_imports  # noqa: E402

script_imports()

from modules.util import create  # noqa: E402
from modules.util.args.TrainArgs import TrainArgs  # noqa: E402
from modules.util.callbacks.TrainCallbacks import TrainCallbacks  # noqa: E402
from modules.util.commands.TrainCommands import TrainCommands  # noqa: E402
from modules.util.config.SecretsConfig import SecretsConfig  # noqa: E402
from modules.util.config.TrainConfig import TrainConfig  # noqa: E402


def _load_config(args) -> TrainConfig:
    cfg = TrainConfig.default_values()
    if args.preset_path is not None:
        with open(args.preset_path, "r", encoding="utf-8") as f:
            cfg.from_dict(json.load(f), migrate=False)
    with open(args.config_path, "r", encoding="utf-8") as f:
        cfg.from_dict(json.load(f), migrate=args.preset_path is None)
    for cv in args.config_values or []:
        key, _, value = cv.partition("=")
        *parents, leaf = key.split(".")
        target = cfg
        for pk in parents:
            target = getattr(target, pk)
        if target.types[leaf] is bool:
            value = value.lower() in ("true", "1", "yes")
        target.from_dict({leaf: value}, migrate=False)
    try:
        sp = "secrets.json" if args.secrets_path is None else args.secrets_path
        with open(sp, "r", encoding="utf-8") as f:
            cfg.secrets = SecretsConfig.default_values().from_dict(json.load(f))
    except FileNotFoundError:
        if args.secrets_path is not None:
            raise
    return cfg


def main():
    args = TrainArgs.parse_args()
    callbacks = TrainCallbacks()
    commands = TrainCommands()
    cfg = _load_config(args)

    trainer = create.create_trainer(cfg, callbacks, commands)
    trainer.start()

    stop_file = os.environ.get("OT_STOP_FILE")
    stop_watch = {"run": True}

    def watch():
        while stop_watch["run"]:
            if stop_file and os.path.isfile(stop_file):
                print("OT_STOP_FILE seen - asking the trainer to save and stop.",
                      flush=True)
                commands.stop()
                return
            time.sleep(2)

    if stop_file:
        threading.Thread(target=watch, daemon=True).start()

    stopped = False
    try:
        trainer.train()                     # returns early if commands.stop()
        stopped = commands.get_stop_command()
    except KeyboardInterrupt:
        stopped = True
        commands.stop()
    finally:
        stop_watch["run"] = False

    # always save what was trained (train.py skips this on KeyboardInterrupt)
    trainer.end()

    if stopped:
        print("STOPPED_EARLY", flush=True)
        sys.exit(3)


if __name__ == "__main__":
    main()
