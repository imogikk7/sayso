"""The last step of every generation route (serving/modal_app.py): guards, parts and alternative_parts.

  finish(result, request, format, previous)   guards.apply on the result (the request and the thread's earlier requests
                                              decide what the user asked for), then the parts of the main answer and,
                                              when the result has `alternatives`, `alternative_parts`: a list parallel
                                              to `alternatives`, each the parts of that alternative (its messages if it
                                              is a series, else [alternative])
"""

import guards
import series


def requested(request, previous=()):
    """Everything the user asked in this thread: what decides whether an introduction was asked for."""
    asked = [str((p if isinstance(p, dict) else {}).get("request") or "") for p in previous or []]
    return " ".join([a for a in asked if a] + [request or ""])


def finish(result, request="", format="message", previous=()):
    asked = requested(request, previous)
    guards.apply(result, asked, format, series.parts_of)
    if isinstance(result.get("text"), str) and format in ("series", series.AUTO):
        result["parts"] = series.parts_of(result["text"], format)
    for reply in result.get("replies") or []:
        if isinstance(reply, dict) and isinstance(reply.get("text"), str) and format in ("series", series.AUTO):
            reply["parts"] = series.parts_of(reply["text"], format)
    for option in result.get("options") or []:
        if isinstance(option, dict) and isinstance(option.get("draft"), str):
            option["draft"] = guards.fix(option["draft"], asked, format) or option["draft"]
    if isinstance(result.get("alternatives"), list):
        result["alternative_parts"] = [series.parts_of(a, format) for a in result["alternatives"]]
    return result
