import streamlit as st
import pandas as pd
import altair as alt
import gspread
from google.oauth2.service_account import Credentials

# --- ページ基本設定 ---
st.set_page_config(
    page_title="㊙りーふch対策 ダッシュボード",
    page_icon="⚔️",
    layout="wide"
)

# --- スプレッドシート接続設定 ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1MQT-B_BtZnaA4qmwOG04T_YFqg36OzxB6Db6PSyHAws/edit"

@st.cache_data(ttl=300)
def load_and_parse_data():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    sheet = client.open_by_url(SPREADSHEET_URL).worksheet("対戦会、成績")
    rows = sheet.get_all_values()

    pokemon_records = []
    match_records = []
    
    current_session = "不明な回"
    mode = None

    for row in rows:
        col0 = row[0].strip() if len(row) > 0 else ""
        col1 = row[1].strip() if len(row) > 1 else ""

        if not any(cell.strip() for cell in row[:6]):
            continue

        # セッション（〇〇回、またはあずあず出張などの見出し）の検出
        if (col0.endswith("回") or "あずあず出張" in col0) and col1 == "":
            current_session = col0
            mode = None
            continue

        if col0 == "ポケモン名":
            mode = "pokemon"
            continue
        elif col0 == "対戦成績":
            mode = None
            continue
        elif col0 == "試合":
            mode = "match"
            continue

        if mode == "pokemon" and col0:
            pokemon_records.append({
                "登場回": current_session,
                "ポケモン名": col0,
                "性格": row[1].strip() if len(row) > 1 else "",
                "努力値・能力ポイント": row[2].strip() if len(row) > 2 else "",
                "持ち物": row[3].strip() if len(row) > 3 else "",
                "技構成": row[4].strip() if len(row) > 4 else "",
                "特性": row[5].strip() if len(row) > 5 else "",
                "備考": row[6].strip() if len(row) > 6 else "",
            })
        elif mode == "match" and col0:
            # 「あずあず出張」の試合は対戦集計から除外
            if "あずあず出張" in current_session or "あずあず出張" in col0:
                continue

            match_records.append({
                "登場回": current_session,
                "対戦相手": col0,
                "勝敗": row[1].strip() if len(row) > 1 else "",
                "りーふの選出": row[2].strip() if len(row) > 2 else "",
                "相手の選出": row[3].strip() if len(row) > 3 else "",
                "対戦メモ": row[4].strip() if len(row) > 4 else "",
            })

    return pd.DataFrame(pokemon_records), pd.DataFrame(match_records)

# --- ヘッダー＆更新ボタン ---
col_title, col_btn = st.columns([5, 1])
with col_title:
    st.title("⚔️ ㊙りーふch対策 ダッシュボード")
    st.caption("Googleスプレッドシートと自動連動中｜構築・選出・対戦履歴データベース（※あずあず出張は戦績集計対象外）")
with col_btn:
    st.write("")
    if st.button("🔄 最新データに更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    df_poke, df_match = load_and_parse_data()
except Exception as e:
    st.error(f"スプレッドシートの読み込みに失敗しました。認証設定を確認してください。\n詳細: {e}")
    st.stop()

# --- タブ切り替え ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 全体サマリー・分析グラフ",
    "🔍 ポケモン個別検索",
    "⚔️ りふなー別戦績",
    "📋 対戦会アーカイブ"
])

# === TAB 1: 全体サマリー＆グラフ ===
with tab1:
    total_matches = len(df_match)
    listener_wins = len(df_match[df_match["勝敗"] == "勝ち"])
    leaf_wins = len(df_match[df_match["勝敗"] == "負け"])
    listener_rate = (listener_wins / total_matches * 100) if total_matches > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("総試合数", f"{total_matches} 戦")
    m2.metric("りふなー勝利", f"{listener_wins} 勝")
    m3.metric("りーふ勝利", f"{leaf_wins} 勝")
    m4.metric("りふなー全体勝率", f"{listener_rate:.1f} %")

    st.divider()

    # --- グラフエリア（2カラム） ---
    g_col1, g_col2 = st.columns(2)

    with g_col1:
        st.subheader("🥧 勝敗比率（全体）")
        if total_matches > 0:
            win_df = pd.DataFrame({
                "区分": ["りーふ勝利", "りふなー勝利"],
                "勝利数": [leaf_wins, listener_wins]
            })
            pie_chart = alt.Chart(win_df).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="勝利数", type="quantitative"),
                color=alt.Color(
                    field="区分",
                    type="nominal",
                    scale=alt.Scale(domain=["りーふ勝利", "りふなー勝利"], range=["#4A90E2", "#FF6B6B"]),
                    legend=alt.Legend(title="")
                ),
                tooltip=["区分", "勝利数"]
            ).properties(height=300)
            st.altair_chart(pie_chart, use_container_width=True)

    with g_col2:
        st.subheader("📈 試合経過ごとの勝率推移")
        if total_matches > 0:
            trend_df = df_match.copy()
            trend_df["試合No"] = range(1, len(trend_df) + 1)
            trend_df["りふなー勝利フラグ"] = (trend_df["勝敗"] == "勝ち").astype(int)
            trend_df["りーふ勝利フラグ"] = (trend_df["勝敗"] == "負け").astype(int)
            trend_df["りふなー累計勝率(%)"] = (trend_df["りふなー勝利フラグ"].cumsum() / trend_df["試合No"] * 100).round(1)
            trend_df["りーふ累計勝率(%)"] = (trend_df["りーふ勝利フラグ"].cumsum() / trend_df["試合No"] * 100).round(1)

            trend_melted = trend_df.melt(
                id_vars=["試合No", "登場回", "対戦相手"],
                value_vars=["りーふ累計勝率(%)", "りふなー累計勝率(%)"],
                var_name="陣営",
                value_name="勝率(%)"
            )
            line_chart = alt.Chart(trend_melted).mark_line(point=True).encode(
                x=alt.X("試合No:Q", title="累計試合数", axis=alt.Axis(tickMinStep=1)),
                y=alt.Y("勝率(%):Q", scale=alt.Scale(domain=[0, 100]), title="勝率 (%)"),
                color=alt.Color(
                    "陣営:N",
                    scale=alt.Scale(domain=["りーふ累計勝率(%)", "りふなー累計勝率(%)"], range=["#4A90E2", "#FF6B6B"]),
                    legend=alt.Legend(title="")
                ),
                tooltip=["試合No", "登場回", "対戦相手", "陣営", "勝率(%)"]
            ).properties(height=300)
            st.altair_chart(line_chart, use_container_width=True)

    st.divider()

    # --- ポケモン採用ランキング（横棒グラフ ＋ テーブル） ---
    st.subheader("🔥 ポケモン構成別 採用ランキング")
    if not df_poke.empty:
        summary_poke = (
            df_poke.groupby(["ポケモン名", "性格", "努力値・能力ポイント", "持ち物"])
            .size()
            .reset_index(name="採用回数")
            .sort_values("採用回数", ascending=False)
        )
        summary_poke["ラベル"] = summary_poke["ポケモン名"] + " (" + summary_poke["性格"] + ")"

        bar_chart = alt.Chart(summary_poke.head(12)).mark_bar(color="#F5A623").encode(
            x=alt.X("採用回数:Q", title="採用回数", axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("ラベル:N", sort="-x", title=""),
            tooltip=["ポケモン名", "性格", "努力値・能力ポイント", "持ち物", "採用回数"]
        ).properties(height=350)
        st.altair_chart(bar_chart, use_container_width=True)

        st.dataframe(summary_poke.drop(columns=["ラベル"]), use_container_width=True, hide_index=True)

# === TAB 2: ポケモン個別検索 ===
with tab2:
    st.subheader("🔍 ポケモン育成論・技構成検索")
    poke_list = ["すべて"] + sorted(df_poke["ポケモン名"].unique().tolist())
    selected_poke = st.selectbox("ポケモンを選択（文字入力で絞り込み可能）", poke_list)

    filtered_poke = df_poke if selected_poke == "すべて" else df_poke[df_poke["ポケモン名"] == selected_poke]
    st.write(f"該当件数: **{len(filtered_poke)} 件**")
    st.dataframe(filtered_poke, use_container_width=True, hide_index=True)

# === TAB 3: りふなー別戦績 ===
with tab3:
    st.subheader("⚔️ りふなー別 対戦成績・選出傾向")
    listener_list = ["すべて"] + sorted(df_match["対戦相手"].unique().tolist())
    selected_listener = st.selectbox("りふなー名を選択", listener_list)

    filtered_match = df_match if selected_listener == "すべて" else df_match[df_match["対戦相手"] == selected_listener]
    
    l_total = len(filtered_match)
    l_win = len(filtered_match[filtered_match["勝敗"] == "勝ち"])
    l_lose = len(filtered_match[filtered_match["勝敗"] == "負け"])
    l_rate = (l_win / l_total * 100) if l_total > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("対戦数", f"{l_total} 戦")
    c2.metric("りふなー戦績", f"{l_win}勝 {l_lose}敗")
    c3.metric("りふなー勝率", f"{l_rate:.1f} %")

    st.dataframe(filtered_match, use_container_width=True, hide_index=True)

# === TAB 4: 対戦会アーカイブ ===
with tab4:
    st.subheader("📋 各回の構築・試合結果アーカイブ")
    sessions = df_poke["登場回"].unique().tolist()
    selected_session = st.selectbox("回を選択", sessions)

    st.markdown(f"### 🐾 {selected_session} の使用構築")
    st.dataframe(df_poke[df_poke["登場回"] == selected_session].drop(columns=["登場回"]), use_container_width=True, hide_index=True)

    st.markdown(f"### 🆚 {selected_session} の対戦結果")
    session_matches = df_match[df_match["登場回"] == selected_session]
    if session_matches.empty:
        st.info("この回の対戦成績は集計対象外です。")
    else:
        st.dataframe(session_matches.drop(columns=["登場回"]), use_container_width=True, hide_index=True)
