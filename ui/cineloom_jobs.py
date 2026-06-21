"""
Cineloom Jobs — a task-history panel for the remote control backend.

Lists recent control jobs (newest first), and for each lets you:
  * import the result as a new strip on the timeline,
  * import the **control map** (Canny) as a strip so you can see what guided it,
  * download the result file to the media folder.

Each generation is its own job (the panel never overwrites existing strips —
imports always go on a free channel). Self-contained: registered via
register_jobs()/unregister_jobs() from the add-on __init__.
"""

import os
import time

import bpy
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import StringProperty, BoolProperty

# Add-on root package, e.g. "bl_ext.user_default.cineloom"
_ROOT = __package__.rsplit(".", 1)[0]

# Backend discovery state (kept fresh by a periodic timer once a URL is set).
_DISCOVERY = {"ok": None, "msg": "Not tested yet", "models": [], "at": 0.0}


def discovery_status():
    return _DISCOVERY


def _do_discovery():
    """Connect to the configured backend and list its models (GET /v1/models)."""
    from ..models.remote_client import CineloomRemoteClient, RemoteConfig
    try:
        client = CineloomRemoteClient(RemoteConfig.from_prefs(_prefs()))
        try:
            client.health()
        except Exception:  # noqa: BLE001
            pass  # /health is optional; the model list is what matters
        models = client.list_models()
        _DISCOVERY.update(ok=True, msg="Connected — %d model(s)" % len(models),
                          models=models, at=time.time())
        return True, _DISCOVERY["msg"]
    except Exception as exc:  # noqa: BLE001
        _DISCOVERY.update(ok=False, msg=str(exc), models=[], at=time.time())
        return False, str(exc)


def _discovery_tick():
    # Persistent connection: refresh the model list periodically while a URL is set.
    try:
        if (getattr(_prefs(), "cineloom_remote_url", "") or "").strip():
            _do_discovery()
    except Exception:  # noqa: BLE001
        pass
    return 300.0  # every 5 minutes


def _prefs():
    return bpy.context.preferences.addons[_ROOT].preferences


def _client():
    from ..models.remote_client import CineloomRemoteClient, RemoteConfig
    cfg = RemoteConfig.from_prefs(
        _prefs(), url_attr="cineloom_control_url",
        env_url="CINELOOM_CONTROL_URL", label="Control Backend URL",
    )
    return CineloomRemoteClient(cfg)


def _media_dir():
    prefs = _prefs()
    d = bpy.path.abspath(getattr(prefs, "generator_ai", "") or "")
    if not d:
        d = os.path.join(os.path.expanduser("~"), "Cineloom_Media")
    os.makedirs(d, exist_ok=True)
    return d


def _add_strip(context, path, name):
    scene = context.scene
    if not scene.sequence_editor:
        scene.sequence_editor_create()
    se = scene.sequence_editor
    coll = se.strips if hasattr(se, "strips") else se.sequences
    channel = 1 + max([s.channel for s in coll] + [0])   # free channel — never overwrite
    coll.new_movie(name=name, filepath=path, channel=channel, frame_start=scene.frame_current)


class CineloomJobItem(PropertyGroup):
    job_id: StringProperty()
    status: StringProperty()
    prompt: StringProperty()
    file_id: StringProperty()
    control_file_id: StringProperty()


class CINELOOM_OT_refresh_jobs(Operator):
    bl_idname = "cineloom.refresh_jobs"
    bl_label = "Refresh Jobs"
    bl_description = "Fetch the recent task history from the control backend"

    def execute(self, context):
        try:
            data = _client()._request("GET", "/v1/jobs", timeout=10)
        except Exception as exc:  # noqa: BLE001
            self.report({'ERROR'}, "Cannot reach control backend: %s" % exc)
            return {'CANCELLED'}
        coll = context.scene.cineloom_jobs
        coll.clear()
        for j in data.get("jobs", []):
            it = coll.add()
            it.job_id = j.get("id", "")
            it.status = j.get("status", "")
            it.prompt = j.get("prompt", "")
            it.file_id = j.get("file_id") or ""
            it.control_file_id = j.get("control_file_id") or ""
        self.report({'INFO'}, "%d task(s)" % len(coll))
        return {'FINISHED'}


class CINELOOM_OT_import_job(Operator):
    bl_idname = "cineloom.import_job"
    bl_label = "Import"
    bl_description = "Download and add this clip as a new strip on the timeline"

    file_id: StringProperty()
    is_control: BoolProperty(default=False)

    def execute(self, context):
        if not self.file_id:
            self.report({'ERROR'}, "Nothing to import yet")
            return {'CANCELLED'}
        try:
            dest = os.path.join(_media_dir(), os.path.basename(self.file_id))
            _client().download_to(self.file_id, dest)
            _add_strip(context, dest, ("control_" if self.is_control else "") + os.path.basename(self.file_id))
        except Exception as exc:  # noqa: BLE001
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, "Imported onto a new channel")
        return {'FINISHED'}


class CINELOOM_OT_download_job(Operator):
    bl_idname = "cineloom.download_job"
    bl_label = "Download"
    bl_description = "Save this clip to the media folder"

    file_id: StringProperty()

    def execute(self, context):
        if not self.file_id:
            return {'CANCELLED'}
        try:
            dest = os.path.join(_media_dir(), os.path.basename(self.file_id))
            _client().download_to(self.file_id, dest)
        except Exception as exc:  # noqa: BLE001
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, "Saved: %s" % dest)
        return {'FINISHED'}


class CINELOOM_OT_test_connection(Operator):
    bl_idname = "cineloom.test_connection"
    bl_label = "Test Connection & Discover Models"
    bl_description = "Reach the backend and list its available models (GET /v1/models)"

    def execute(self, context):
        ok, msg = _do_discovery()
        self.report({'INFO'} if ok else {'ERROR'}, msg)
        return {'FINISHED'} if ok else {'CANCELLED'}


class SEQUENCER_PT_cineloom_jobs(Panel):
    bl_label = "Cineloom Jobs"
    bl_idname = "SEQUENCER_PT_cineloom_jobs"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Cineloom"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def draw(self, context):
        layout = self.layout
        layout.operator("cineloom.refresh_jobs", icon="FILE_REFRESH")
        jobs = context.scene.cineloom_jobs
        if not len(jobs):
            layout.label(text="No tasks — Refresh after generating.", icon="INFO")
            return
        for it in jobs:
            box = layout.box()
            label = it.prompt[:40] if it.prompt else it.job_id[:8]
            box.label(text="[%s] %s" % (it.status, label))
            row = box.row(align=True)
            done = it.status in ("succeeded", "completed", "done")
            if it.file_id and done:
                op = row.operator("cineloom.import_job", text="Result", icon="SEQUENCE")
                op.file_id = it.file_id; op.is_control = False
                op = row.operator("cineloom.download_job", text="", icon="IMPORT")
                op.file_id = it.file_id
            if it.control_file_id:
                op = row.operator("cineloom.import_job", text="Control map", icon="IMAGE_DATA")
                op.file_id = it.control_file_id; op.is_control = True


_jobs_classes = (
    CineloomJobItem,
    CINELOOM_OT_refresh_jobs,
    CINELOOM_OT_import_job,
    CINELOOM_OT_download_job,
    CINELOOM_OT_test_connection,
    SEQUENCER_PT_cineloom_jobs,
)


def register_jobs():
    for cls in _jobs_classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cineloom_jobs = bpy.props.CollectionProperty(type=CineloomJobItem)
    if not bpy.app.timers.is_registered(_discovery_tick):
        bpy.app.timers.register(_discovery_tick, first_interval=300.0, persistent=True)


def unregister_jobs():
    try:
        if bpy.app.timers.is_registered(_discovery_tick):
            bpy.app.timers.unregister(_discovery_tick)
    except Exception:  # noqa: BLE001
        pass
    try:
        del bpy.types.Scene.cineloom_jobs
    except Exception:  # noqa: BLE001
        pass
    for cls in reversed(_jobs_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
