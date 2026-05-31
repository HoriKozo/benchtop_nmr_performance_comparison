# 卓上NMR 測定時間・性能比較アプリ

このStreamlitアプリは、卓上NMR装置の ^1H感度、推定測定時間、分解能、設置面積、体積、重量などを比較するためのツールです。
<img width="650" height="293" alt="MG Competition2" src="https://github.com/user-attachments/assets/7127f48e-6540-465a-893a-6e60eab1050c" />

## 主な機能

- 2機種の卓上NMRを並列比較
- ^1H感度から必要測定時間を推定
- Excelファイルから定義済みモデルを選択
- 将来機種や競合機種向けの任意感度入力
- 分解能（Hz）の比較
- サイズ比較表示：
  - 3Dサイズ比較
  - 設置面積オーバーレイ表示
  - 比率サマリー表示
- 1日あたりの測定処理数を試算

## 測定時間計算
<img width="650" height="314" alt="MG App Top" src="https://github.com/user-attachments/assets/4cef5bd8-8eca-492a-a3bf-74816e3b0fe5" />

推定測定時間は、以下の関係式に基づいて計算されます。

```text
必要測定時間 = 基準測定時間 × (基準感度 / 比較対象感度)^2
本計算は、S/N比が概ね測定時間の平方根に比例することを前提としています。
