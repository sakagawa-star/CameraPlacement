# 技術スタック情報

## プロジェクト基盤

| 項目 | 値 | 根拠 |
|------|-----|------|
| 言語 | Python >=3.12 | `pyproject.toml` `requires-python` |
| パッケージ管理 | uv | CLAUDE.md 開発ルール |
| ビルドシステム | setuptools >=75.0 | `pyproject.toml` `build-system` |
| 対象OS | 未定義 | パッケージ定義・設計書に記載なし |

## ライブラリ一覧

### ランタイム依存

| ライブラリ名 | バージョン | 用途（1行） | 使用箇所（モジュール名） | 選定理由（1行） |
|-------------|-----------|------------|------------------------|----------------|
| numpy | >=2.4.2 | ベクトル・行列演算、空間計算のバッチ処理 | models.environment, models.camera, models.activity, core.frustum, core.occlusion, core.visibility, evaluation.coverage, evaluation.angle_score, evaluation.projection_score, evaluation.evaluator, visualization.viewer, placement.patterns, optimization.objective, optimization.optimizer（14ファイル） | 全幾何計算の基盤。ブロードキャストによるベクトル化処理で高速化 |
| plotly | >=6.6.0 | 3Dインタラクティブ可視化（HTML出力） | visualization.viewer, optimization.optimizer（2ファイル） | HTML出力対応、マウス操作による3D回転・ズーム、軽量（open3dのVTK依存を回避） |
| scipy | >=1.17.1 | 差分進化法による最適化 | optimization.optimizer（1ファイル） | `scipy.optimize.differential_evolution` を使用。6台×6自由度=36次元の連続最適化に適合 |

### 開発依存

| ライブラリ名 | バージョン | 用途（1行） | 使用箇所 | 選定理由（1行） |
|-------------|-----------|------------|---------|----------------|
| pytest | >=9.0.2 | ユニットテスト・統合テスト実行 | tests/（全テストファイル） | Python標準的テストフレームワーク |

### 標準ライブラリ（主要なもの）

| ライブラリ名 | 用途（1行） | 使用箇所（モジュール名） |
|-------------|------------|------------------------|
| dataclasses | 不変データ構造の定義（frozen=True） | models.environment, models.camera, models.activity, evaluation 各モジュール, placement.patterns, placement.comparison, optimization.objective, optimization.optimizer |
| enum | ActivityType 等の列挙型定義 | models.activity, placement.patterns |
| logging | ログ出力 | optimization.optimizer |
| pathlib | ファイルパス操作 | visualization.viewer, placement.comparison, optimization.optimizer |
| time | 処理時間計測 | optimization.optimizer |

### 設計書に記載があるが採用されなかったライブラリ

| ライブラリ名 | 記載箇所 | 不採用理由 |
|-------------|---------|-----------|
| open3d | CLAUDE.md（想定ライブラリ） | VTK依存が重い。plotly で軽量かつ環境非依存な3D可視化を実現 |
| matplotlib | F11 設計検討時 | 3Dインタラクティビティが不十分 |
| pyvista | F11 設計検討時 | 用途に対してオーバースペック |

## バージョン固定ポリシー

| 項目 | 内容 |
|------|------|
| 管理ファイル | `pyproject.toml`（ランタイム: `dependencies`、開発: `dependency-groups.dev`） |
| ロックファイル | `uv.lock`（再現可能なインストール用） |
| バージョン指定方針 | `>=下限` 指定（互換性のある最新バージョンを許容） |
| インストールコマンド | `uv add <パッケージ名>`（ランタイム）、`uv add --dev <パッケージ名>`（開発） |

## 制約・禁止事項

### 技術的制約

| 制約 | 根拠 | 対象 |
|------|------|------|
| Python 3.12 以上必須 | 型ヒント・最新構文の使用 | pyproject.toml, 全設計書 |
| カメラ台数は6台固定 | ハードウェア仕様 | CLAUDE.md, 全モジュール |
| セルフオクルージョンは簡略化 | 初期段階の方針 | CLAUDE.md, F05-F06 |
| レンズ歪み無視 | TV歪曲 0.4% で無視可能 | CLAUDE.md, F02 |

### アーキテクチャ制約

| 制約 | 理由 | 対象 |
|------|------|------|
| プリセットは外部設定ファイル不使用（ハードコード） | I/O複雑性の回避 | F12 設計書 |
| データクラスは frozen=True | 不変性の保証、ハッシュ可能性 | F02, F12 設計書 |
| 座標は tuple 型を使用（numpy array ではなく） | frozen dataclass との互換性 | F02, F12 設計書 |

### 使用禁止ライブラリ

明示的に禁止されているライブラリの定義は未定義。ただし、設計方針として以下を回避している：

- **open3d**: VTK依存が重く環境構築が困難なため回避（F11 設計書）
- **重量級フレームワーク全般**: 軽量・環境非依存を重視する方針（F11 設計書）

## 不整合事項

現時点で、設計書の記載と実コード間の不整合は検出されなかった。
