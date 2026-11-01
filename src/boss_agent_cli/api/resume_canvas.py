"""Conservative reconstruction of browser-rendered resume text (not API JSON).

Never claim complete coverage: folded/lazy content may not have been drawn.
Keep the evidence text even when a project cannot be mapped unambiguously.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math
import re
from typing import Any


def reconstruct_text(draws: list[dict[str, Any]]) -> str:
	canvases: dict[str, dict[tuple[float, float, str], str]] = defaultdict(dict)
	for row in draws[:100000]:
		if not isinstance(row, dict) or not isinstance(row.get("text"), str):
			continue
		try:
			x, y = float(row["x"]), float(row["y"])
		except (KeyError, TypeError, ValueError):
			continue
		if not math.isfinite(x) or not math.isfinite(y):
			continue
		text = row["text"]
		if text.startswith("Boss-TraceID"):
			continue
		canvases[str(row.get("canvas", 0))][(round(y), round(x, 1), text)] = text
	if not canvases:
		return ""
	# Do not mix scratch canvases or overlay coordinates with the resume canvas.
	main = max(canvases.values(), key=lambda rows: sum(len(t) for t in rows.values()))
	lines: dict[float, list[tuple[float, str]]] = defaultdict(list)
	for (y, x, text) in sorted(main):
		lines[y].append((x, text))
	return "\n".join("".join(t for _, t in line).strip() for line in lines.values()).strip()


def enrich_canvas_resume(summary: dict[str, Any], canvas: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
	info = deepcopy(summary)
	draws = canvas.get("draws") or []
	text = reconstruct_text(draws if isinstance(draws, list) else [])
	info["renderedText"] = text
	reasons = []
	if not canvas.get("composited"):
		reasons.append("legacy_uncomposited_capture")
	if not canvas.get("reached_bottom"):
		reasons.append("scroll_incomplete")
	if not canvas.get("height_measured"):
		reasons.append("resume_height_unverified")
	if canvas.get("render_stalled"):
		reasons.append("render_stalled")
	if canvas.get("unsupported"):
		reasons.append("unsupported_canvas_operation")
	if "查看全部" in text or "展开全部" in text:
		reasons.append("expand_controls_present")
	if canvas.get("capped"):
		reasons.append("capture_limit")
	if canvas.get("timed_out"):
		reasons.append("capture_timeout")
	projects = info.get("geekProjExpList") or []
	lines = text.splitlines()
	anchors: list[tuple[int, dict[str, Any]]] = []
	for project in projects:
		name = project.get("name")
		if not name:
			continue
		matches = [i for i, line in enumerate(lines) if line.startswith(name) or line.startswith("项目经验" + name)]
		if len(matches) == 1:
			anchors.append((matches[0], project))
		else:
			reasons.append("project_anchor_ambiguous")
	anchors.sort(key=lambda pair: pair[0])
	# Missing/duplicate titles can otherwise attach a neighbour's body to a project.
	if len(anchors) != len(projects) or len({i for i, _ in anchors}) != len(anchors):
		anchors = []
	sections = ("教育经历", "工作经历", "实习经历", "资格证书", "专业技能", "志愿者经历", "社团经历", "个人优势", "期望职位")
	for index, (start, project) in enumerate(anchors):
		end = anchors[index + 1][0] if index + 1 < len(anchors) else len(lines)
		for i in range(start + 1, end):
			if lines[i].startswith(sections):
				end = i
				break
		body = lines[start + 1:end]
		# The first line after the title is normally the date range.
		if body and re.fullmatch(r"\d{4}[.\-/]\d{1,2}\s*[-—~至]\s*(?:\d{4}[.\-/]\d{1,2}|至今)", body[0]):
			body = body[1:]
		description = "\n".join(body).replace("查看全部", "").replace("展开全部", "").strip()
		if description and not project.get("projectDescription"):
			project["projectDescription"] = description
			project["descriptionSource"] = "canvas"
	if any(not p.get("projectDescription") for p in projects):
		reasons.append("project_description_missing")
	# Preserve other sections rather than discarding text not represented in the
	# WASM summary. Work and education bodies are copied, never semantically split.
	section_names = ("最近关注", "期望职位", "个人优势", "工作经历", "实习经历", "项目经验", "项目经历",
		"教育经历", "社团经历", "志愿者经历", "所获荣誉", "资格证书", "专业技能")
	parts: dict[str, list[str]] = {"基本信息与自述": []}
	current = "基本信息与自述"
	for line in lines:
		if line.startswith("为妥善保护牛人"):
			current = "平台提示"
		else:
			for heading in section_names:
				if line.startswith(heading):
					current = heading
					break
		parts.setdefault(current, []).append(line)
	info["renderedSections"] = {key: "\n".join(value) for key, value in parts.items() if value}
	for list_key, name_key, target_key, section_keys in (
		("geekWorkExpList", "company", "responsibility", ("工作经历", "实习经历")),
		("geekEduExpList", "school", "description", ("教育经历",)),
	):
		items = info.get(list_key) or []
		section_lines = "\n".join(info["renderedSections"].get(k, "") for k in section_keys).splitlines()
		positions = []
		for item in items:
			name = item.get(name_key)
			matches = [i for i, line in enumerate(section_lines) if name and
				(line.startswith(name) or any(line.startswith(k + name) for k in section_keys))]
			if len(matches) == 1:
				positions.append((matches[0], item))
		if len(positions) != len(items) or len({i for i, _ in positions}) != len(items):
			if items:
				reasons.append(list_key + "_mapping_ambiguous")
			continue
		positions.sort(key=lambda pair: pair[0])
		for index, (start, item) in enumerate(positions):
			end = positions[index + 1][0] if index + 1 < len(positions) else len(section_lines)
			body = section_lines[start + 1:end]
			if body and re.fullmatch(r"\d{4}(?:[.\-/]\d{1,2})?\s*[-—~至]\s*(?:\d{4}(?:[.\-/]\d{1,2})?|至今)", body[0]):
				body = body[1:]
			if body and not item.get(target_key):
				item[target_key] = "\n".join(body)
	# Full traversal describes only rendered content, not fields withheld by BOSS.
	if not text:
		reasons.append("no_rendered_text")
	return info, {
		"source": "official_iframe_canvas",
		"completeness": "partial" if reasons else "rendered_complete",
		"reasons": list(dict.fromkeys(reasons)),
		"raw_is_api_response": False,
		"text_length": len(text),
		"reached_bottom": bool(canvas.get("reached_bottom")),
		"scroll_steps": canvas.get("scroll_steps", 0),
		"snapshots": canvas.get("snapshots", 0),
		"content_height": canvas.get("content_height"),
		"measured_height": canvas.get("measured_height"),
	}
