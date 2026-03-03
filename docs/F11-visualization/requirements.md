# 要求仕様書: F11 3D可視化

## 1. プロジェクト概要

- **何を作るか**: 病室空間・ベッド・カメラ・視錐台・カバレッジマップを plotly で3Dインタラクティブ表示する可視化モジュール
- **なぜ作るか**: カメラ配置の評価結果を視覚的に確認するため。F13（配置比較）でパターン間の違いを直感的に把握し、F15（最適化結果）を視覚的に検証するために使用する
- **誰が使うか**: F13（配置比較モジュール）、F15（最適化エンジン）、開発者
- **どこで使うか**: Python 3.12 ローカル環境（ブラウザでHTMLファイルを閲覧）

## 2. 用語定義

| 用語 | 定義 |
|------|------|
| シーン (scene) | 部屋・ベッド・カメラ・視錐台・カバレッジ等の全要素を含む3D plotly Figure |
| トレース (trace) | plotly Figure 内の1つの描画要素。`go.Scatter3d` や `go.Mesh3d` のインスタンス |
| ワイヤフレーム (wireframe) | AABB や視錐台の辺のみを線で描画した表現 |
| カバレッジマップ (coverage map) | グリッド点群を視認カメラ数で色分けした散布図 |
| 視錐台 (frustum) | カメラのFOVによる視野範囲を示す四角錐台 |
| カラースケール (colorscale) | グリッド点の色とカメラ数の対応。`RdYlGn`（赤→黄→緑） |
| 表示用far距離 (display far) | 視錐台の表示用ファークリップ距離。可視化のために実際のfar=10mより短くする |
| トレースグループ (trace group) | 凡例で一括表示/非表示できるトレースのまとまり |

## 3. 機能要件

### FR-01: 部屋ワイヤフレーム描画

部屋のAABB境界を12本の辺で描画する。

- 入力: `Room` インスタンス
- 出力: 部屋のAABBワイヤフレーム（12辺）を表す `go.Scatter3d` トレースのリスト（要素数1）
- 線の色: 黒 (`rgb(0,0,0)`)
- 線の幅: 2
- トレース名: `"Room"`
- 受け入れ基準: 部屋の8頂点を結ぶ12本の辺がワイヤフレームとして表示されること

### FR-02: ベッド描画

ベッドのAABBを半透明の3Dボックスとして描画する。

- 入力: `Room` インスタンス（`room.bed` を使用）
- 出力: ベッドを表す `go.Mesh3d` トレースのリスト（要素数1）
- 色: ライトブルー (`lightblue`)
- 不透明度: 0.3
- トレース名: `"Bed"`
- 受け入れ基準: ベッドの位置・サイズが半透明ボックスとして表示されること

### FR-03: カメラ位置・方向描画

カメラの位置をマーカーで、前方方向を矢印線で描画する。

- 入力: `list[Camera]`
- 出力: トレースのリスト（要素数2）:
  - カメラ位置マーカー: `go.Scatter3d`（`mode='markers+text'`）。1トレースに全カメラを含む
  - 前方方向線: `go.Scatter3d`（`mode='lines'`）。1トレースに全カメラの方向線を含む
- マーカーサイズ: 6
- マーカーシンボル: `'diamond'`
- マーカーの色: `rgb(0, 0, 0)`（黒）
- テキスト: `"C1"`, `"C2"`, ..., `"C{M}"` （M=カメラ台数）。`textposition='top center'`
- 方向線の長さ: カメラ位置から前方方向に0.3m
- 方向線の色: `rgb(0, 0, 0)`（黒）
- 方向線の幅: 3
- トレース名: カメラ位置は `"Cameras"`、方向線は `"Camera Direction"`
- 受け入れ基準: 各カメラが番号ラベル付きマーカーと方向線で表示されること。カメラ0台の場合は空のトレースリスト（要素数0）を返すこと

### FR-04: 視錐台ワイヤフレーム描画

各カメラの視錐台（四角錐台）を12辺のワイヤフレームで描画する。

- 入力: `list[Camera]`, `near: float`（デフォルト0.1）, `far: float`（表示用far距離、デフォルト3.0）
- 出力: `go.Scatter3d` トレースのリスト（カメラ1台につき1トレース、計M個）
- 各カメラに異なる色を割り当てる。カラーパレットは以下の6色:
  - C1: `rgb(31, 119, 180)` (青)
  - C2: `rgb(255, 127, 14)` (橙)
  - C3: `rgb(44, 160, 44)` (緑)
  - C4: `rgb(214, 39, 40)` (赤)
  - C5: `rgb(148, 103, 189)` (紫)
  - C6: `rgb(140, 86, 75)` (茶)
  - M > 6 の場合はインデックス `i % 6` で循環する
- 線の幅: 1.5
- トレース名: `"Frustum C1"`, `"Frustum C2"`, ...
- `legendgroup`: `"frustums"` （全視錐台を一括で表示/非表示できる）
- 受け入れ基準: 各カメラの視錐台が異なる色のワイヤフレームで表示されること。`FrustumChecker.get_frustum_corners()` の8頂点を結ぶ12辺であること。カメラ0台の場合は空のリスト（要素数0）を返すこと

### FR-05: カバレッジマップ描画

グリッド点群を視認カメラ数に応じた色で描画する。

- 入力: `grid_points: np.ndarray` shape (N, 3)、`visible_counts: np.ndarray` shape (N,) dtype int、`num_cameras: int`（カラースケール上限、デフォルト6）
- 出力: `go.Scatter3d` トレースのリスト（要素数1）
- `mode='markers'`
- マーカーサイズ: 3
- カラースケール: `RdYlGn`（赤=0台、黄=中間、緑=最大）
- `cmin=0`, `cmax=num_cameras`
- カラーバーのタイトル: `"Visible Cameras"`
- トレース名: `"Coverage"`
- 受け入れ基準: グリッド点が視認カメラ数に応じて色分け表示され、カラーバーが表示されること。N=0の場合は空の `go.Scatter3d`（データなし）のリスト（要素数1）を返すこと

### FR-06: シーン組み立て

FR-01〜FR-05の全要素を1つの3D plotly Figure に組み立てる。

- 入力:
  - `room: Room` （必須）
  - `cameras: list[Camera]` （必須）
  - `coverage_result: CoverageResult | None` （任意、デフォルト None）
  - `show_frustums: bool` （デフォルト True）
  - `show_grid: bool` （デフォルト True。coverage_result が None の場合は show_grid=True でもグリッドを表示しない）
  - `frustum_far: float` （表示用far距離、デフォルト 3.0）
  - `title: str` （デフォルト `"Camera Placement Visualization"`）
- 出力: `go.Figure`
- レイアウト設定:
  - タイトル: `title` パラメータの値
  - X軸ラベル: `"X [m]"`
  - Y軸ラベル: `"Y [m]"`
  - Z軸ラベル: `"Z [m]"`
  - アスペクト比: `aspectmode='data'`（等スケール）
  - 図のサイズ: `width=1000, height=800`
- 受け入れ基準:
  - `create_scene(room, cameras)` でカバレッジなしのシーンが生成できること
  - `create_scene(room, cameras, coverage_result)` で全要素を含むシーンが生成できること
  - `show_frustums=False` で視錐台トレースが含まれないこと
  - `show_grid=False` でカバレッジトレースが含まれないこと

### FR-07: HTML出力

plotly Figure をスタンドアロンHTMLファイルに保存する。

- 入力: `go.Figure`, `filepath: str | Path`
- 出力: HTMLファイル（plotly.js を埋め込んだスタンドアロンファイル）
- `include_plotlyjs=True`（オフラインで閲覧可能）
- 戻り値: 保存先の `Path` オブジェクト
- 親ディレクトリが存在しない場合: 自動作成する（`mkdir(parents=True, exist_ok=True)`）
- 受け入れ基準: 指定パスにHTMLファイルが生成され、ブラウザで開くとインタラクティブ3Dシーンが表示されること

### FR-08: 凡例によるトレース表示切替

各トレースグループを凡例クリックで表示/非表示を切り替えられる。

- plotly のデフォルトの凡例クリック挙動を使用する（追加実装不要）
- 各トレースに `name` を設定することで自動的に凡例に表示される
- 視錐台トレースは `legendgroup="frustums"` で一括制御可能
- 受け入れ基準: 凡例をクリックすると対応するトレースが表示/非表示になること

## 4. 非機能要求

### パフォーマンス

- `create_scene` の実行時間: N=5,000 グリッド点・6台カメラで 1秒以内（トレース生成のみ。plotly のレンダリング時間は含まない）
- HTMLファイルサイズ: N=5,000 グリッド点で 10MB 以下
- N=10,000 グリッド点でのブラウザ上のインタラクティブ操作性能は plotly に依存し、本モジュールでは検証・保証しない

### 対応環境

- Python 3.12
- plotly >= 5.0（`go.Scatter3d`, `go.Mesh3d`, `go.Figure` を使用）
- ブラウザ: plotly がサポートする主要ブラウザ（Chrome, Firefox, Edge）

## 5. 制約条件

- 使用ライブラリ: plotly（`uv add plotly` でインストール）、numpy（既存）
- F01, F02, F03, F07 の既存インターフェースを変更しない
- `FrustumChecker.get_frustum_corners()` を視錐台の頂点取得に使用する
- カバレッジマップの入力は `CoverageResult`（F07）から取得する
- セルフオクルージョンは表示しない（モデルに含まれていないため）

## 6. 優先順位

| 要件 | MoSCoW |
|------|--------|
| FR-01 部屋ワイヤフレーム | Must |
| FR-02 ベッド描画 | Must |
| FR-03 カメラ位置・方向 | Must |
| FR-04 視錐台ワイヤフレーム | Must |
| FR-05 カバレッジマップ | Must |
| FR-06 シーン組み立て | Must |
| FR-07 HTML出力 | Must |
| FR-08 凡例による表示切替 | Should |

## 7. エッジケースの期待動作

| ケース | 期待動作 |
|--------|---------|
| cameras が空リスト | カメラ・視錐台トレースは空（部屋とベッドのみ表示）。エラーにならない |
| cameras が1台のみ | 1台分のカメラマーカー・方向線・視錐台を表示 |
| coverage_result が None | カバレッジマップを表示しない（部屋・ベッド・カメラ・視錐台のみ） |
| coverage_result の grid_points が空 (0, 3) | カバレッジトレースはデータなしの Scatter3d を返す |
| show_frustums=False | 視錐台トレースがシーンに含まれない |
| show_frustums=False かつ frustum_far <= 0 | ValueError（show_frustums の値に関わらず frustum_far はバリデーションされる） |
| show_grid=False | カバレッジトレースがシーンに含まれない |
| coverage_result=None かつ show_grid=True | カバレッジマップを表示しない（coverage_result がないため） |
| frustum_far <= 0 | ValueError |
| frustum_far > 10.0 | 視錐台が大きくなるが正常動作。実用上は 1.0〜5.0 を推奨 |
| num_cameras = 0 | cmax=0 となり plotly がフォールバック描画する。本モジュールではバリデーションしない |
| filepath の親ディレクトリが存在しない | 自動作成してHTML保存 |
| カメラ台数が7台以上 | カラーパレットが i%6 で循環。正常動作 |

## 8. スコープ外

- 品質スコア（F10 `point_quality_scores`）による色分け表示（F13/F15 で必要になった場合に拡張）
- 活動ボリューム境界の表示（複雑化を避けるため初期実装では対象外）
- アニメーション機能
- GUI ウィジェット（plotly のビルトインインタラクション以外）
- カメラ画像のシミュレーション表示
- 2D投影ビュー
