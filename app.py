import streamlit as st
import googlemaps
import pandas as pd
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv
import os
import re

# .envファイルをロード
load_dotenv()

# Google Maps APIキー
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Streamlit ページ設定
st.set_page_config(page_title="配送ルート最適化", layout="wide")

# Google Maps クライアント初期化
try:
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
    st.info("Google Maps クライアントが正常に初期化されました。")
except Exception as e:
    st.error(f"Google Maps クライアントの初期化に失敗しました: {e}")
    st.stop()

# サンプル住所
SAMPLE_ADDRESSES = [
    "東京都新宿区新宿3-1-1",
    "東京都新宿区西新宿2-8-1",
    "東京都新宿区大久保1-1-1",
    "東京都新宿区高田馬場1-1-1",
    "東京都新宿区四谷1-1-1"
]

# API料金
API_COST = {
    "Geocoding API": 0.5,  # 住所1件あたり 0.5円
    "Distance Matrix API": 10.5,  # 要素1000個あたり 10.5円
    "Directions API": 10.5,  # リクエスト1回あたり 10.5円
}

# セッション状態を初期化
if "API_USAGE" not in st.session_state:
    st.session_state.API_USAGE = {
        "Geocoding API": 0,
        "Distance Matrix API": 0,
        "Directions API": 0,
    }
if "calculation_result" not in st.session_state:
    st.session_state.calculation_result = None

def calculate_route(addresses):
    """配送ルートの最適化とAPI使用量計算"""
    try:
        # Geocoding API: ジオコーディング (住所 -> 緯度経度)
        locations = []
        for addr in addresses:
            geocode_result = gmaps.geocode(addr)
            st.session_state.API_USAGE["Geocoding API"] += 1  # 1リクエスト消費
            if not geocode_result:
                st.error(f"住所が見つかりません: {addr}")
                st.stop()
            location = geocode_result[0]['geometry']['location']
            locations.append(location)

        # Distance Matrix API: 距離計算
        num_addresses = len(addresses)
        elements_count = num_addresses * (num_addresses - 1)  # N*(N-1) 要素
        st.session_state.API_USAGE["Distance Matrix API"] += elements_count  # 要素数をリクエストにカウント

        # Directions API: 経路計算
        directions_result = gmaps.directions(
            origin=locations[0],
            destination=locations[-1],
            waypoints=locations[1:-1],
            optimize_waypoints=True,
            mode="driving",
            language="ja"
        )
        st.session_state.API_USAGE["Directions API"] += 1  # 1リクエスト消費

        return {
            'locations': locations,
            'directions': directions_result
        }
    except Exception as e:
        st.error(f"ルート計算中にエラーが発生しました: {e}")
        return None

def display_map(directions_result):
    """地図上にルートを描画"""
    st.subheader("最適ルート地図")
    map_center = directions_result[0]['legs'][0]['start_location']
    folium_map = folium.Map(location=[map_center['lat'], map_center['lng']], zoom_start=13)

    for leg in directions_result[0]['legs']:
        start = [leg['start_location']['lat'], leg['start_location']['lng']]
        end = [leg['end_location']['lat'], leg['end_location']['lng']]
        folium.Marker(start, popup="Start").add_to(folium_map)
        folium.Marker(end, popup="End").add_to(folium_map)
        folium.PolyLine(
            locations=[[step['start_location']['lat'], step['start_location']['lng']] for step in leg['steps']] +
                     [[leg['end_location']['lat'], leg['end_location']['lng']]],
            color="blue",
            weight=5,
            opacity=0.8
        ).add_to(folium_map)

    st_folium(folium_map, width=700)

def display_route_details(directions_result, addresses):
    """ルート詳細を表示"""
    st.subheader("最適ルート詳細")
    waypoint_order = directions_result[0]['waypoint_order']
    ordered_addresses = [addresses[i + 1] for i in waypoint_order]
    ordered_addresses.insert(0, addresses[0])
    ordered_addresses.append(addresses[-1])

    for idx, (start, end) in enumerate(zip(ordered_addresses[:-1], ordered_addresses[1:])):
        st.write(f"**{idx + 1}. {start} → {end}**")
        leg = directions_result[0]['legs'][idx]
        distance = leg['distance']['text']
        duration = leg['duration']['text']
        st.write(f"- 距離: {distance}, 時間: {duration}")

        for step in leg['steps']:
            instructions = re.sub('<.*?>', '', step['html_instructions'])
            step_distance = step['distance']['text']
            st.write(f"  - {instructions} ({step_distance})")
        st.write("---")

def calculate_costs():
    """API使用量に基づく料金計算"""
    total_cost = 0
    st.subheader("API使用量と料金計算")
    for api, usage in st.session_state.API_USAGE.items():
        if api == "Distance Matrix API":
            usage /= 1000  # 要素を1000単位に換算
        cost = usage * API_COST[api]
        total_cost += cost
        st.write(f"- {api}: {st.session_state.API_USAGE[api]} リクエスト, 費用: ¥{cost:.2f}")
    st.write(f"**合計費用: ¥{total_cost:.2f}**")

def main():
    st.title("配送ルート最適化アプリ")
    st.write("Google Maps APIを使用して、配送ルートを最適化します。")

    addresses = st.text_area(
        "住所を改行で区切って入力してください",
        value="\n".join(SAMPLE_ADDRESSES)
    ).split("\n")
    addresses = [addr.strip() for addr in addresses if addr.strip()]

    if st.button("ルート計算"):
        with st.spinner("計算中..."):
            st.session_state.calculation_result = calculate_route(addresses)

    if st.session_state.calculation_result:
        result = st.session_state.calculation_result
        st.success("ルート計算が完了しました！")
        display_map(result['directions'])
        display_route_details(result['directions'], addresses)
        calculate_costs()

if __name__ == "__main__":
    main()
