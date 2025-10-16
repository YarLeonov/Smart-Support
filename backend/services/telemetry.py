import json, time, uuid, sys
def log_event(event, **kw):
    rec = {"ts": time.time(), "event": event, **kw}
    print(json.dumps(rec, ensure_ascii=False), file=sys.stderr)
def new_request_id():
    return str(uuid.uuid4())
