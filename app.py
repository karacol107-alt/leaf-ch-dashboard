import streamlit as st
import pandas as pd
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

        if col0.endswith("回") and col1 == "":
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
    st.caption("Googleスプレッドシートと自動連動中｜構築・選出・対戦履歴データベース")
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
    "📊 全体サマリー・採用率",
    "🔍 ポケモン個別検索",
    "⚔️ りふなー別戦績",
    "📋 対戦会アーカイブ"
])

# === TAB 1: 全体サマリー ===
with tab1:
    total_matches = len(df_match)
    leaf_wins = len(df_match[df_match["勝敗"] == "勝ち"])
    listener_wins = len(df_match[df_match["勝敗"] == "負け"])
    listener_rate = (listener_wins / total_matches * 100) if total_matches > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("総試合数", f"{total_matches} 戦")
    m2.metric("りふなー勝利", f"{listener_wins} 勝")
    m3.metric("りーふ勝利", f"{leaf_wins} 勝")
    m4.metric("りふなー全体勝率", f"{listener_rate:.1f} %")

    st.divider()
    st.subheader("🔥 ポケモン構成別 採用ランキング")
    if not df_poke.empty:
        summary_poke = (
            df_poke.groupby(["ポケモン名", "性格", "努力値・能力ポイント", "持ち物"])
            .size()
            .reset_index(name="採用回数")
            .sort_values("採用回数", ascending=False)
        )
        st.dataframe(summary_poke, use_container_width=True, hide_index=True)

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
    l_win = len(filtered_match[filtered_match["勝敗"] == "負け"])
    l_lose = len(filtered_match[filtered_match["勝敗"] == "勝ち"])
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
    st.dataframe(df_match[df_match["登場回"] == selected_session].drop(columns=["登場回"]), use_container_width=True, hide_index=True)
