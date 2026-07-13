"""Build a self-contained HTML dashboard for branch tag coverage data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.domain.tag_models import Coverage


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "visualization" / "branch_tag_coverage.json"
DEFAULT_OUTPUT = ROOT / "visualization" / "branch_tag_coverage.html"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SCP支部タグカバレッジ</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f5f7fa;
        --panel: #ffffff;
        --panel-alt: #f0f4f8;
        --text: #1d252c;
        --muted: #637083;
        --line: #d8dee7;
        --line-strong: #b8c2d0;
        --focus: #214d87;
        --shadow: 0 10px 24px rgba(28, 39, 55, 0.08);
        --name: #2f6f73;
        --alias: #3f6fb5;
        --unused-replacement: #bd8421;
        --unused-open: #b45c2a;
        --policy-omit: #8d6a2f;
        --override: #7859a6;
        --crosswalk: #16807a;
        --unhandled: #b84040;
      }

      * {
        box-sizing: border-box;
      }

      html {
        min-width: 320px;
      }

      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family:
          system-ui,
          -apple-system,
          BlinkMacSystemFont,
          "Segoe UI",
          sans-serif;
        line-height: 1.5;
      }

      button,
      input,
      select {
        font: inherit;
      }

      button {
        cursor: pointer;
      }

      .shell {
        width: min(1440px, 100%);
        margin: 0 auto;
        padding: 24px;
      }

      .topbar {
        display: grid;
        grid-template-columns: minmax(260px, 1fr) auto;
        gap: 24px;
        align-items: end;
        padding: 8px 0 18px;
        border-bottom: 1px solid var(--line);
      }

      .title-block {
        min-width: 0;
      }

      h1,
      h2,
      h3,
      p {
        margin: 0;
      }

      h1 {
        font-size: clamp(1.55rem, 2.2vw, 2.4rem);
        line-height: 1.1;
        letter-spacing: 0;
      }

      .source-line {
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.92rem;
      }

      .actions {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
        flex-wrap: wrap;
      }

      .command {
        display: inline-flex;
        min-height: 38px;
        align-items: center;
        justify-content: center;
        gap: 8px;
        border: 1px solid var(--line-strong);
        border-radius: 7px;
        background: var(--panel);
        color: var(--text);
        padding: 7px 12px;
        white-space: nowrap;
      }

      .command:hover {
        border-color: var(--focus);
      }

      .grid {
        display: grid;
        gap: 16px;
      }

      .metrics {
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin: 22px 0 18px;
      }

      .metric {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: var(--shadow);
        min-height: 104px;
        padding: 16px;
        display: grid;
        align-content: space-between;
        gap: 8px;
      }

      .metric-label {
        color: var(--muted);
        font-size: 0.84rem;
      }

      .metric-value {
        font-size: clamp(1.7rem, 3vw, 2.35rem);
        font-weight: 740;
        line-height: 1;
      }

      .metric-sub {
        color: var(--muted);
        font-size: 0.85rem;
      }

      .layout {
        display: grid;
        grid-template-columns: minmax(340px, 440px) minmax(0, 1fr);
        gap: 18px;
        align-items: start;
      }

      .panel {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: var(--shadow);
        min-width: 0;
      }

      .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        padding: 16px 18px 10px;
      }

      .panel-title {
        font-size: 1rem;
        letter-spacing: 0;
      }

      .panel-kicker {
        color: var(--muted);
        font-size: 0.82rem;
        white-space: nowrap;
      }

      .controls {
        padding: 14px 18px 18px;
        border-bottom: 1px solid var(--line);
        display: grid;
        gap: 12px;
      }

      .control-row {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }

      .field {
        display: grid;
        gap: 5px;
        min-width: 0;
      }

      .field label {
        color: var(--muted);
        font-size: 0.78rem;
      }

      .field input,
      .field select {
        width: 100%;
        min-height: 38px;
        border: 1px solid var(--line-strong);
        border-radius: 7px;
        padding: 7px 9px;
        background: var(--panel);
        color: var(--text);
      }

      .field input:focus,
      .field select:focus,
      .command:focus,
      .status-filter:focus,
      .branch-row:focus {
        outline: 3px solid rgba(33, 77, 135, 0.2);
        outline-offset: 1px;
      }

      .quick-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .status-filters {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .status-filter {
        min-height: 34px;
        display: inline-flex;
        align-items: center;
        gap: 7px;
        border: 1px solid var(--line-strong);
        border-radius: 7px;
        background: var(--panel);
        color: var(--text);
        padding: 6px 9px;
      }

      .status-filter[aria-pressed="false"] {
        color: var(--muted);
        background: var(--panel-alt);
      }

      .swatch {
        width: 0.8rem;
        height: 0.8rem;
        border-radius: 3px;
        flex: 0 0 auto;
        background: var(--status-color);
      }

      .branch-list {
        padding: 4px 10px 12px;
        max-height: 730px;
        overflow: auto;
      }

      .branch-row {
        width: 100%;
        display: grid;
        grid-template-columns: 56px minmax(0, 1fr) 76px;
        gap: 10px;
        align-items: center;
        min-height: 58px;
        border: 0;
        border-radius: 7px;
        background: transparent;
        color: var(--text);
        padding: 8px;
        text-align: left;
      }

      .branch-row:hover,
      .branch-row.active {
        background: var(--panel-alt);
      }

      .branch-code {
        font-weight: 740;
      }

      .branch-meta {
        display: grid;
        gap: 5px;
        min-width: 0;
      }

      .branch-bar {
        display: flex;
        width: 100%;
        height: 12px;
        overflow: hidden;
        border-radius: 6px;
        background: #e5e9ef;
      }

      .branch-bar span {
        display: block;
        min-width: 1px;
        background: var(--status-color);
      }

      .branch-caption {
        color: var(--muted);
        font-size: 0.78rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .branch-score {
        text-align: right;
        color: var(--muted);
        font-variant-numeric: tabular-nums;
        font-size: 0.82rem;
      }

      .detail-grid {
        display: grid;
        grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
        gap: 16px;
        padding: 0 18px 18px;
      }

      .donut-wrap {
        display: grid;
        justify-items: center;
        gap: 14px;
        padding: 8px 0;
      }

      .donut {
        width: min(240px, 70vw);
        aspect-ratio: 1;
        border-radius: 50%;
        background: var(--donut);
        position: relative;
        box-shadow: inset 0 0 0 1px var(--line);
      }

      .donut::after {
        content: "";
        position: absolute;
        inset: 18%;
        border-radius: 50%;
        background: var(--panel);
        box-shadow: inset 0 0 0 1px var(--line);
      }

      .donut-label {
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        z-index: 1;
        text-align: center;
        font-variant-numeric: tabular-nums;
      }

      .donut-label strong {
        display: block;
        font-size: 1.55rem;
        line-height: 1.1;
      }

      .donut-label span {
        color: var(--muted);
        font-size: 0.8rem;
      }

      .legend {
        display: grid;
        gap: 8px;
        width: 100%;
      }

      .legend-item {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr) auto;
        align-items: center;
        gap: 8px;
        color: var(--muted);
        font-size: 0.83rem;
      }

      .legend-item strong {
        color: var(--text);
        font-weight: 640;
      }

      .insights {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }

      .insight {
        border: 1px solid var(--line);
        border-radius: 8px;
        min-height: 88px;
        padding: 12px;
        background: var(--panel-alt);
        min-width: 0;
      }

      .insight-label {
        color: var(--muted);
        font-size: 0.78rem;
      }

      .insight-value {
        margin-top: 4px;
        font-size: 1.2rem;
        font-weight: 740;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .insight-sub {
        margin-top: 3px;
        color: var(--muted);
        font-size: 0.78rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .table-wrap {
        border-top: 1px solid var(--line);
        overflow: auto;
        max-height: 670px;
      }

      table {
        width: 100%;
        border-collapse: collapse;
        min-width: 820px;
      }

      th,
      td {
        padding: 9px 10px;
        border-bottom: 1px solid var(--line);
        text-align: left;
        vertical-align: top;
      }

      th {
        position: sticky;
        top: 0;
        z-index: 1;
        background: var(--panel-alt);
        color: var(--muted);
        font-size: 0.78rem;
        font-weight: 680;
      }

      td {
        font-size: 0.88rem;
      }

      .tag-name {
        font-weight: 700;
        word-break: break-all;
      }

      .tag-detail {
        color: var(--muted);
        font-size: 0.78rem;
        word-break: break-all;
      }

      .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border: 1px solid color-mix(in srgb, var(--status-color) 55%, var(--line));
        border-radius: 999px;
        padding: 4px 8px;
        background: color-mix(in srgb, var(--status-color) 10%, white);
        color: var(--text);
        white-space: nowrap;
      }

      .sample-list {
        color: var(--muted);
        word-break: break-all;
      }

      .empty-state {
        padding: 30px 18px;
        color: var(--muted);
        text-align: center;
      }

      .hidden {
        display: none !important;
      }

      :root {
        --bg: #eef3f7;
        --panel-alt: #f6f8fb;
        --panel-soft: #edf2f6;
        --text: #15202b;
        --muted: #627084;
        --line: #d5dde6;
        --line-strong: #aebbc9;
        --focus: #1f5d80;
        --shadow: 0 16px 34px rgba(27, 43, 63, 0.08);
        --shadow-soft: 0 8px 18px rgba(27, 43, 63, 0.06);
        --name: #2d7477;
        --alias: #3d6fbd;
        --unused-replacement: #c78a18;
        --unused-open: #b95c2e;
        --policy-omit: #9b7430;
        --override: #7659ad;
        --crosswalk: #238d86;
        --unhandled: #bd4246;
        --sidebar: #f8fafc;
      }

      .app-frame {
        width: 100%;
        min-height: 100vh;
        display: grid;
        grid-template-columns: 238px minmax(0, 1fr);
      }

      .sidebar {
        position: sticky;
        top: 0;
        height: 100vh;
        padding: 20px 16px;
        background: var(--sidebar);
        border-right: 1px solid var(--line);
        display: grid;
        grid-template-rows: auto 1fr auto;
        gap: 24px;
      }

      .brand {
        display: grid;
        grid-template-columns: 36px minmax(0, 1fr);
        gap: 10px;
        align-items: center;
      }

      .brand-mark {
        width: 36px;
        height: 36px;
        border-radius: 8px;
        background:
          linear-gradient(135deg, rgba(45, 116, 119, 0.95), rgba(61, 111, 189, 0.9));
        box-shadow: var(--shadow-soft);
      }

      .brand-title,
      .brand-sub {
        display: block;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .brand-title {
        font-size: 0.95rem;
        font-weight: 760;
        line-height: 1.15;
      }

      .brand-sub {
        margin-top: 2px;
        color: var(--muted);
        font-size: 0.74rem;
      }

      .nav-stack {
        display: grid;
        align-content: start;
        gap: 6px;
      }

      .nav-item {
        display: grid;
        grid-template-columns: 12px minmax(0, 1fr);
        gap: 9px;
        align-items: center;
        min-height: 34px;
        padding: 7px 9px;
        border-radius: 7px;
        color: var(--muted);
        font-size: 0.84rem;
      }

      .nav-item.active {
        background: #e9f1f3;
        color: var(--text);
        font-weight: 700;
      }

      .nav-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: var(--status-color, var(--line-strong));
      }

      .sidebar-note {
        color: var(--muted);
        font-size: 0.76rem;
        line-height: 1.45;
      }

      .main-area {
        min-width: 0;
      }

      .shell {
        width: min(1500px, 100%);
        padding: 22px 28px 30px;
      }

      .topbar {
        grid-template-columns: minmax(280px, 1fr) auto;
        align-items: center;
        padding: 2px 0 18px;
      }

      h1 {
        font-size: clamp(1.55rem, 2.1vw, 2.25rem);
      }

      .command {
        min-height: 40px;
        padding: 8px 13px;
        box-shadow: var(--shadow-soft);
      }

      .metrics {
        margin: 18px 0;
      }

      .metric {
        min-height: 116px;
        padding: 15px;
        gap: 12px;
        position: relative;
        overflow: hidden;
      }

      .metric::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        background: var(--metric-color, var(--name));
      }

      .metric-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
      }

      .metric-accent {
        width: 30px;
        height: 30px;
        border-radius: 8px;
        background: color-mix(in srgb, var(--metric-color, var(--name)) 14%, white);
        border: 1px solid color-mix(in srgb, var(--metric-color, var(--name)) 28%, var(--line));
        position: relative;
        flex: 0 0 auto;
      }

      .metric-accent::after {
        content: "";
        position: absolute;
        inset: 9px;
        border-radius: 999px;
        background: var(--metric-color, var(--name));
      }

      .layout {
        grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
      }

      .panel {
        overflow: hidden;
      }

      .controls {
        padding: 14px 18px 16px;
        background: linear-gradient(180deg, #ffffff, var(--panel-alt));
      }

      .field input,
      .field select {
        min-height: 40px;
        padding: 8px 10px;
      }

      .status-filter {
        background: rgba(255, 255, 255, 0.84);
      }

      .branch-list {
        max-height: 820px;
        padding-bottom: 14px;
      }

      .branch-row {
        grid-template-columns: 52px minmax(0, 1fr) 66px;
      }

      .branch-row.active {
        box-shadow: inset 3px 0 0 var(--focus);
      }

      .detail-grid {
        grid-template-columns: minmax(240px, 310px) minmax(0, 1fr);
        padding: 16px 18px 18px;
      }

      .donut {
        width: min(244px, 70vw);
      }

      .insight {
        min-height: 104px;
        padding: 14px;
        background: linear-gradient(180deg, #f8fafc, var(--panel-soft));
      }

      .table-wrap {
        max-height: 590px;
      }

      @media (prefers-color-scheme: dark) {
        :root {
          color-scheme: dark;
          --bg: #11161d;
          --panel: #1b222b;
          --panel-alt: #222b36;
          --panel-soft: #202935;
          --sidebar: #161d26;
          --text: #e9edf2;
          --muted: #a8b2c0;
          --line: #33404e;
          --line-strong: #465566;
          --focus: #9fc2ef;
          --shadow: 0 10px 24px rgba(0, 0, 0, 0.24);
        }

        .branch-bar {
          background: #303a45;
        }

        .status-pill {
          background: color-mix(in srgb, var(--status-color) 18%, var(--panel));
        }

        .controls,
        .insight {
          background: var(--panel-alt);
        }

        .nav-item.active {
          background: #222d39;
        }
      }

      @media (max-width: 1080px) {
        .app-frame {
          grid-template-columns: 1fr;
        }

        .sidebar {
          display: none;
        }

        .layout,
        .detail-grid {
          grid-template-columns: 1fr;
        }

        .branch-list {
          max-height: 520px;
        }
      }

      @media (max-width: 760px) {
        .shell {
          padding: 16px;
        }

        .topbar {
          grid-template-columns: 1fr;
          align-items: start;
        }

        .actions {
          justify-content: flex-start;
        }

        .metrics,
        .control-row,
        .insights {
          grid-template-columns: 1fr;
        }

        .branch-row {
          grid-template-columns: 48px minmax(0, 1fr) 66px;
        }
      }
    </style>
  </head>
  <body>
    <div class="app-frame">
      <aside class="sidebar" aria-label="ダッシュボードナビゲーション">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true"></span>
          <span>
            <span class="brand-title">SCP Tag Coverage</span>
            <span class="brand-sub">JP mapping audit</span>
          </span>
        </div>
        <nav class="nav-stack" aria-label="分類サマリー">
          <span class="nav-item active"><span class="nav-dot" style="--status-color: var(--name)"></span>カバレッジ</span>
          <span class="nav-item"><span class="nav-dot" style="--status-color: var(--alias)"></span>JP別名注記</span>
          <span class="nav-item"><span class="nav-dot" style="--status-color: var(--unused-replacement)"></span>非使用タグ</span>
          <span class="nav-item"><span class="nav-dot" style="--status-color: var(--policy-omit)"></span>翻訳時省略</span>
          <span class="nav-item"><span class="nav-dot" style="--status-color: var(--override)"></span>上書き辞書</span>
          <span class="nav-item"><span class="nav-dot" style="--status-color: var(--crosswalk)"></span>公式対訳表</span>
          <span class="nav-item"><span class="nav-dot" style="--status-color: var(--unhandled)"></span>申請・確認必要</span>
        </nav>
        <p class="sidebar-note">JPタグリストと支部コーパス由来タグの対応状況</p>
      </aside>

      <main class="main-area">
        <div class="shell">
          <header class="topbar">
            <div class="title-block">
              <h1>支部タグカバレッジ</h1>
              <p class="source-line" id="sourceLine"></p>
            </div>
            <div class="actions">
              <button class="command" id="resetButton" type="button">リセット</button>
              <button class="command" id="exportButton" type="button">TSV出力</button>
            </div>
          </header>

          <section class="grid metrics" id="metrics" aria-label="全体指標"></section>

          <section class="layout">
            <aside class="panel" aria-label="支部一覧">
              <div class="panel-header">
                <h2 class="panel-title">支部別の分布</h2>
                <span class="panel-kicker" id="branchCount"></span>
              </div>
              <div class="branch-list" id="branchList"></div>
            </aside>

            <section class="panel detail-panel" aria-label="タグ詳細">
              <div class="panel-header">
                <h2 class="panel-title" id="detailTitle">全支部</h2>
                <span class="panel-kicker" id="visibleCount"></span>
              </div>

              <div class="controls">
                <div class="control-row">
                  <div class="field">
                    <label for="branchSelect">支部</label>
                    <select id="branchSelect"></select>
                  </div>
                  <div class="field">
                    <label for="sortSelect">並び順</label>
                    <select id="sortSelect">
                      <option value="pages-desc">使用ページ数</option>
                      <option value="unhandled-first">申請・確認必要を優先</option>
                      <option value="status">分類</option>
                      <option value="tag">タグ名</option>
                      <option value="branch">支部</option>
                    </select>
                  </div>
                  <div class="field">
                    <label for="queryInput">検索</label>
                    <input id="queryInput" type="search" placeholder="tag / JP / slug" />
                  </div>
                </div>
                <div class="quick-actions">
                  <button class="command" id="allStatusesButton" type="button">全分類</button>
                  <button class="command" id="unhandledButton" type="button">申請・確認必要のみ</button>
                  <button class="command" id="handledButton" type="button">対応済みのみ</button>
                </div>
                <div class="status-filters" id="statusFilters" aria-label="分類フィルター"></div>
              </div>

              <div class="detail-grid">
                <div class="donut-wrap">
                  <div class="donut" id="donut" role="img" aria-label="分類比率">
                    <div class="donut-label">
                      <div>
                        <strong id="donutValue"></strong>
                        <span id="donutText"></span>
                      </div>
                    </div>
                  </div>
                  <div class="legend" id="legend"></div>
                </div>
                <div class="insights" id="insights"></div>
              </div>

              <div class="table-wrap" id="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>支部</th>
                      <th>タグ</th>
                      <th>分類</th>
                      <th>JP/置換</th>
                      <th>ページ</th>
                      <th>サンプル</th>
                    </tr>
                  </thead>
                  <tbody id="tagRows"></tbody>
                </table>
              </div>
              <div class="empty-state hidden" id="emptyState">該当なし</div>
            </section>
          </section>
        </div>
      </main>
    </div>

    <script type="application/json" id="coverage-data">__DATA_JSON__</script>
    <script>
      const rawData = JSON.parse(document.getElementById("coverage-data").textContent);
      const statusOrder = [
        "jp_tag_name",
        "jp_tag_alias",
        "jp_unused_replacement",
        "jp_unused_no_single_replacement",
        "jp_translation_policy_omit",
        "curated_override_only",
        "official_crosswalk",
        "unhandled",
      ];
      const statusMeta = {
        jp_tag_name: {
          label: "JP登録名",
          color: "var(--name)",
        },
        jp_tag_alias: {
          label: "JP別名注記",
          color: "var(--alias)",
        },
        jp_unused_replacement: {
          label: "JP非使用・置換あり",
          color: "var(--unused-replacement)",
        },
        jp_unused_no_single_replacement: {
          label: "JP非使用・単一置換なし",
          color: "var(--unused-open)",
        },
        jp_translation_policy_omit: {
          label: "JP翻訳方針で省略",
          color: "var(--policy-omit)",
        },
        curated_override_only: {
          label: "ローカル上書きのみ",
          color: "var(--override)",
        },
        official_crosswalk: {
          label: "公式対訳表",
          color: "var(--crosswalk)",
        },
        unhandled: {
          label: "タグ申請・確認必要",
          color: "var(--unhandled)",
        },
      };
      const tableLimit = 500;
      const allTags = rawData.branches.flatMap((branch) =>
        branch.tags.map((tag) => ({
          ...tag,
          branch: branch.branch,
          branchPageCount: branch.page_count,
          branchTagCount: branch.tag_count,
        })),
      );
      const branchMap = new Map(rawData.branches.map((branch) => [branch.branch, branch]));
      const state = {
        branch: "all",
        sort: "pages-desc",
        query: "",
        statuses: new Set(statusOrder),
      };
      const els = {
        sourceLine: document.getElementById("sourceLine"),
        metrics: document.getElementById("metrics"),
        branchCount: document.getElementById("branchCount"),
        branchList: document.getElementById("branchList"),
        branchSelect: document.getElementById("branchSelect"),
        sortSelect: document.getElementById("sortSelect"),
        queryInput: document.getElementById("queryInput"),
        statusFilters: document.getElementById("statusFilters"),
        detailTitle: document.getElementById("detailTitle"),
        visibleCount: document.getElementById("visibleCount"),
        donut: document.getElementById("donut"),
        donutValue: document.getElementById("donutValue"),
        donutText: document.getElementById("donutText"),
        legend: document.getElementById("legend"),
        insights: document.getElementById("insights"),
        tagRows: document.getElementById("tagRows"),
        tableWrap: document.getElementById("tableWrap"),
        emptyState: document.getElementById("emptyState"),
      };

      const numberFormatter = new Intl.NumberFormat("ja-JP");
      const formatNumber = (value) => numberFormatter.format(value);
      const formatPercent = (value, total) => (total ? `${Math.round((value / total) * 100)}%` : "0%");
      const cssColor = (status) => statusMeta[status].color;
      const statusLabel = (status) => statusMeta[status].label;

      function escapeHtml(value) {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");
      }

      function summarize(rows) {
        const counts = Object.fromEntries(statusOrder.map((status) => [status, 0]));
        let jpListHandled = 0;
        let translatorHandled = 0;
        let copyable = 0;
        let pages = 0;
        for (const row of rows) {
          counts[row.status] += 1;
          if (row.jp_list_handled) jpListHandled += 1;
          if (row.translator_handled) translatorHandled += 1;
          if (row.copy_allowed) copyable += 1;
          pages += row.page_count;
        }
        return {
          total: rows.length,
          counts,
          jpListHandled,
          translatorHandled,
          copyable,
          pages,
          unhandled: counts.unhandled,
        };
      }

      function branchCopyAllowedCount(branch) {
        return branch.tags.filter((tag) => tag.copy_allowed).length;
      }

      function filteredRows() {
        const query = state.query.trim().toLowerCase();
        return allTags.filter((row) => {
          if (state.branch !== "all" && row.branch !== state.branch) return false;
          if (!state.statuses.has(row.status)) return false;
          if (!query) return true;
          return [
            row.branch,
            row.tag,
            row.jp_tag,
            row.replacement,
            ...(row.sample_slugs || []),
          ]
            .filter(Boolean)
            .some((value) => String(value).toLowerCase().includes(query));
        });
      }

      function sortRows(rows) {
        const statusRank = Object.fromEntries(statusOrder.map((status, index) => [status, index]));
        const sorted = [...rows];
        sorted.sort((a, b) => {
          if (state.sort === "unhandled-first") {
            const aRank = a.status === "unhandled" ? 0 : a.translator_handled ? 2 : 1;
            const bRank = b.status === "unhandled" ? 0 : b.translator_handled ? 2 : 1;
            if (aRank !== bRank) return aRank - bRank;
            return b.page_count - a.page_count || a.tag.localeCompare(b.tag, "ja");
          }
          if (state.sort === "status") {
            return statusRank[a.status] - statusRank[b.status] || b.page_count - a.page_count;
          }
          if (state.sort === "tag") {
            return a.tag.localeCompare(b.tag, "ja") || a.branch.localeCompare(b.branch);
          }
          if (state.sort === "branch") {
            return a.branch.localeCompare(b.branch) || b.page_count - a.page_count;
          }
          return b.page_count - a.page_count || a.tag.localeCompare(b.tag, "ja");
        });
        return sorted;
      }

      function renderMetrics() {
        const summary = summarize(allTags);
        const branchCount = rawData.branches.length;
        const cards = [
          ["支部", branchCount, "コーパス由来の翻訳元", "var(--name)"],
          ["タグ", summary.total, `${formatNumber(summary.pages)}ページ出現`, "var(--alias)"],
          ["コピー可能", summary.copyable, formatPercent(summary.copyable, summary.total), "var(--crosswalk)"],
          ["申請・確認必要", summary.unhandled, formatPercent(summary.unhandled, summary.total), "var(--unhandled)"],
        ];
        els.metrics.innerHTML = cards
          .map(
            ([label, value, sub, color]) => `
              <article class="metric" style="--metric-color: ${color}">
                <div class="metric-head">
                  <div class="metric-label">${escapeHtml(label)}</div>
                  <span class="metric-accent" aria-hidden="true"></span>
                </div>
                <div class="metric-value">${formatNumber(value)}</div>
                <div class="metric-sub">${escapeHtml(sub)}</div>
              </article>
            `,
          )
          .join("");
      }

      function renderBranchSelect() {
        const options = [
          '<option value="all">全支部</option>',
          ...rawData.branches.map(
            (branch) =>
              `<option value="${escapeHtml(branch.branch)}">${escapeHtml(branch.branch)} (${formatNumber(branch.tag_count)})</option>`,
          ),
        ];
        els.branchSelect.innerHTML = options.join("");
      }

      function renderStatusFilters() {
        els.statusFilters.innerHTML = statusOrder
          .map(
            (status) => `
              <button class="status-filter" type="button" data-status="${status}" aria-pressed="${state.statuses.has(status)}" style="--status-color: ${cssColor(status)}">
                <span class="swatch" aria-hidden="true"></span>
                <span>${escapeHtml(statusLabel(status))}</span>
              </button>
            `,
          )
          .join("");
      }

      function renderBranches() {
        const branches = [...rawData.branches].sort((a, b) => {
          const aUnhandled = a.status_counts.unhandled || 0;
          const bUnhandled = b.status_counts.unhandled || 0;
          const aRatio = aUnhandled / Math.max(a.tag_count, 1);
          const bRatio = bUnhandled / Math.max(b.tag_count, 1);
          return bRatio - aRatio || b.tag_count - a.tag_count || a.branch.localeCompare(b.branch);
        });
        els.branchCount.textContent = `${formatNumber(branches.length)}支部`;
        els.branchList.innerHTML = branches
          .map((branch) => {
            const copyable = branchCopyAllowedCount(branch);
            const active = state.branch === branch.branch ? " active" : "";
            const segments = statusOrder
              .map((status) => {
                const count = branch.status_counts[status] || 0;
                const pct = (count / branch.tag_count) * 100;
                return `<span title="${escapeHtml(statusLabel(status))}: ${formatNumber(count)}" style="width: ${pct}%; --status-color: ${cssColor(status)}"></span>`;
              })
              .join("");
            return `
              <button class="branch-row${active}" type="button" data-branch="${escapeHtml(branch.branch)}">
                <span class="branch-code">${escapeHtml(branch.branch)}</span>
                <span class="branch-meta">
                  <span class="branch-bar">${segments}</span>
                  <span class="branch-caption">${formatNumber(copyable)} / ${formatNumber(branch.tag_count)} コピー可能</span>
                </span>
                <span class="branch-score">${formatPercent(copyable, branch.tag_count)}</span>
              </button>
            `;
          })
          .join("");
      }

      function donutGradient(counts, total) {
        if (!total) return "conic-gradient(#d8dee7 0deg 360deg)";
        let cursor = 0;
        const stops = [];
        for (const status of statusOrder) {
          const count = counts[status] || 0;
          if (!count) continue;
          const start = cursor;
          cursor += (count / total) * 360;
          stops.push(`${cssColor(status)} ${start}deg ${cursor}deg`);
        }
        return `conic-gradient(${stops.join(", ")})`;
      }

      function renderDetail(rows) {
        const summary = summarize(rows);
        const selectedBranch = state.branch === "all" ? null : branchMap.get(state.branch);
        const title = selectedBranch ? `${selectedBranch.branch}支部` : "全支部";
        els.detailTitle.textContent = title;
        els.visibleCount.textContent = `${formatNumber(rows.length)}タグ`;
        els.donut.style.setProperty("--donut", donutGradient(summary.counts, summary.total));
        els.donutValue.textContent = formatPercent(summary.copyable, summary.total);
        els.donutText.textContent = "コピー可能";
        els.legend.innerHTML = statusOrder
          .map(
            (status) => `
              <div class="legend-item" style="--status-color: ${cssColor(status)}">
                <span class="swatch" aria-hidden="true"></span>
                <strong>${escapeHtml(statusLabel(status))}</strong>
                <span>${formatNumber(summary.counts[status] || 0)}</span>
              </div>
            `,
          )
          .join("");

        const mostUsed = rows.reduce((best, row) => (!best || row.page_count > best.page_count ? row : best), null);
        const topUnhandled = rows
          .filter((row) => row.status === "unhandled")
          .sort((a, b) => b.page_count - a.page_count)[0];
        const localOnly = summary.counts.curated_override_only || 0;
        const unused = (summary.counts.jp_unused_replacement || 0) + (summary.counts.jp_unused_no_single_replacement || 0);
        const insightItems = [
          ["使用最大", mostUsed ? mostUsed.tag : "-", mostUsed ? `${mostUsed.branch} / ${formatNumber(mostUsed.page_count)}ページ` : ""],
          ["申請候補最多", topUnhandled ? topUnhandled.tag : "-", topUnhandled ? `${topUnhandled.branch} / ${formatNumber(topUnhandled.page_count)}ページ` : ""],
          ["ローカル上書き", localOnly, formatPercent(localOnly, summary.total)],
          ["JP非使用扱い", unused, formatPercent(unused, summary.total)],
        ];
        els.insights.innerHTML = insightItems
          .map(
            ([label, value, sub]) => `
              <article class="insight">
                <div class="insight-label">${escapeHtml(label)}</div>
                <div class="insight-value">${typeof value === "number" ? formatNumber(value) : escapeHtml(value)}</div>
                <div class="insight-sub">${escapeHtml(sub)}</div>
              </article>
            `,
          )
          .join("");
      }

      function renderTable(rows) {
        const sorted = sortRows(rows);
        const visible = sorted.slice(0, tableLimit);
        els.tableWrap.classList.toggle("hidden", visible.length === 0);
        els.emptyState.classList.toggle("hidden", visible.length !== 0);
        els.visibleCount.textContent =
          sorted.length > tableLimit
            ? `${formatNumber(tableLimit)} / ${formatNumber(sorted.length)}タグ`
            : `${formatNumber(sorted.length)}タグ`;
        els.tagRows.innerHTML = visible
          .map((row) => {
            const jpValue = row.jp_tag || row.replacement || "";
            const source = row.replacement && row.jp_tag ? `${row.jp_tag} → ${row.replacement}` : jpValue;
            const sample = (row.sample_slugs || []).slice(0, 3).join(", ");
            const action = row.translation_action || "";
            return `
              <tr>
                <td>${escapeHtml(row.branch)}</td>
                <td>
                  <div class="tag-name">${escapeHtml(row.tag)}</div>
                  <div class="tag-detail">rank ${formatNumber(row.rank)}</div>
                </td>
                <td>
                  <span class="status-pill" style="--status-color: ${cssColor(row.status)}">
                    <span class="swatch" aria-hidden="true"></span>
                    ${escapeHtml(statusLabel(row.status))}
                  </span>
                </td>
                <td>
                  ${source ? escapeHtml(source) : '<span class="tag-detail">-</span>'}
                  <div class="tag-detail">${escapeHtml(action)}</div>
                </td>
                <td>${formatNumber(row.page_count)}</td>
                <td class="sample-list">${escapeHtml(sample)}</td>
              </tr>
            `;
          })
          .join("");
      }

      function renderSourceLine() {
        const corpus = rawData.source?.corpus_root || "";
        els.sourceLine.textContent = `schema${rawData.schema_version} / ${rawData.branches.length}支部 / ${formatNumber(allTags.length)}タグ / corpus参照`;
        els.sourceLine.title = corpus;
      }

      function render() {
        els.branchSelect.value = state.branch;
        els.sortSelect.value = state.sort;
        els.queryInput.value = state.query;
        const rows = filteredRows();
        renderStatusFilters();
        renderBranches();
        renderDetail(rows);
        renderTable(rows);
      }

      function setStatuses(statuses) {
        state.statuses = new Set(statuses);
        render();
      }

      function exportTsv() {
        const rows = sortRows(filteredRows());
        const headers = ["branch", "tag", "status", "translation_action", "copy_allowed", "jp_tag", "replacement", "page_count", "rank", "sample_slugs"];
        const lines = [headers.join("\\t")];
        for (const row of rows) {
          lines.push(
            headers
              .map((key) => {
                const value = key === "sample_slugs" ? (row.sample_slugs || []).join(",") : row[key];
                return String(value ?? "").replaceAll("\\t", " ").replaceAll("\\n", " ");
              })
              .join("\\t"),
          );
        }
        const blob = new Blob([lines.join("\\n") + "\\n"], { type: "text/tab-separated-values;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = "branch_tag_coverage_filtered.tsv";
        anchor.click();
        URL.revokeObjectURL(url);
      }

      function bindEvents() {
        els.branchSelect.addEventListener("change", (event) => {
          state.branch = event.target.value;
          render();
        });
        els.sortSelect.addEventListener("change", (event) => {
          state.sort = event.target.value;
          render();
        });
        els.queryInput.addEventListener("input", (event) => {
          state.query = event.target.value;
          render();
        });
        els.statusFilters.addEventListener("click", (event) => {
          const button = event.target.closest("button[data-status]");
          if (!button) return;
          const status = button.dataset.status;
          if (state.statuses.has(status)) {
            if (state.statuses.size === 1) return;
            state.statuses.delete(status);
          } else {
            state.statuses.add(status);
          }
          render();
        });
        els.branchList.addEventListener("click", (event) => {
          const button = event.target.closest("button[data-branch]");
          if (!button) return;
          state.branch = button.dataset.branch;
          render();
        });
        document.getElementById("allStatusesButton").addEventListener("click", () => setStatuses(statusOrder));
        document.getElementById("unhandledButton").addEventListener("click", () => setStatuses(["unhandled"]));
        document
          .getElementById("handledButton")
          .addEventListener("click", () => setStatuses(statusOrder.filter((status) => status !== "unhandled")));
        document.getElementById("resetButton").addEventListener("click", () => {
          state.branch = "all";
          state.sort = "pages-desc";
          state.query = "";
          state.statuses = new Set(statusOrder);
          render();
        });
        document.getElementById("exportButton").addEventListener("click", exportTsv);
      }

      renderSourceLine();
      renderMetrics();
      renderBranchSelect();
      bindEvents();
      render();
    </script>
  </body>
</html>
"""


def build_html(data: Coverage) -> str:
    embedded_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    embedded_json = (
        embedded_json.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return HTML_TEMPLATE.replace("__DATA_JSON__", embedded_json)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        data = cast(Coverage, json.loads(args.input.read_text(encoding="utf-8")))
        html = build_html(data)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html, encoding="utf-8")
    except (OSError, ValueError) as err:
        print(f"エラー: HTML可視化生成に失敗しました: {err}")
        sys.exit(1)
    print(f"HTML可視化を生成しました: {args.output}")


if __name__ == "__main__":
    main()
