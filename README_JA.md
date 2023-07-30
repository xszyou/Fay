[`中文`](https://github.com/TheRamU/Fay/blob/main/README.md)
[`English`](https://github.com/TheRamU/Fay/blob/main/README_EN.md)

<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay">
    <h1>FAY</h1>
	<h3>Fay デジタルヒューマンアシスタント</h3>
</div>


Fay デジタルヒューマンアシスタントエディションは、Fay オープンソースプロジェクトの重要なブランチであり、インテリジェントデジタルアシスタントのためのオープンソースソリューションの構築に焦点を当てています。感情分析、NLP 処理、音声合成、音声出力など、さまざまな機能モジュールをカスタマイズして組み合わせることができる柔軟なモジュール設計を提供しています。Fay Digital Assistant Edition は、インテリジェントでパーソナライズされた多機能デジタル・アシスタント・アプリケーションを構築するための強力なツールとリソースを開発者に提供します。このエディションにより、開発者は様々なシナリオやドメインに適用可能なデジタルアシスタントを容易に作成し、インテリジェントな音声対話やパーソナライズされたサービスをユーザーに提供することができます。



## Fay デジタルアシスタントエディション

ProTip:ショッピング版は別ブランチに移動しました。[`fay-sales-edition`](https://github.com/TheRamU/Fay/tree/fay-sales-edition)

![](images/controller.png)

*アシスタントフェイコントローラー使用: 音声通信、音声とテキスト返信; **テキスト通信、テキスト返信;** UE、live2d、xuniren を接続するには、再生用のパネルを閉じる必要があります。*




## **アシスタント Fay コントローラー**

  Remote Android　　　　　　Local PC　　　　　Remote PC

　　　　　└─────────────┼─────────────┘


　　　　　　Aliyun API ─┐　　　│


　　　　　 　　　　　　├──      ASR　　　


 　  　　 　　　 [FunASR](https://www.bilibili.com/video/BV1qs4y1g74e) ─┘　　　│　　 　 ┌─ Yuan 1.0

　　　　　　　　　　　　　　　  │　　 　 ├─ [LingJu](https://www.bilibili.com/video/BV1NW4y1D76a/)

　　　 　　　　　　　　　　　NLP ────┼─ [GPT/ChatGPT](https://www.bilibili.com/video/BV1Dg4y1V7pn)

　　　　　　　　　　　　　　　│　　 　 ├─ [Rasa+ChatGLM-6B](https://www.bilibili.com/video/BV1D14y1f7pr)

　　　　　　　　 Azure ─┐　 　 │　　 　 ├─ [VisualGLM](https://www.bilibili.com/video/BV1mP411Q7mj)

　　　　　 　 Edge TTS ─┼──     TTS 　  　 └─ [RWKV](https://www.bilibili.com/video/BV1yu41157zB)

　   　　[Open source TTS](https://www.bilibili.com/read/cv25192534) ─┘　  │　　 　

　　　　　　　　　　　　　　    │　　 　

　　　　　　　　　　　　　　   │　　 　

　　　 ┌──────────┬────┼───────┬─────────┐

Remote Android　　[Live2D](https://www.bilibili.com/video/BV1sx4y1d775/?vd_source=564eede213b9ddfa9a10f12e5350fd64)　　 [UE](https://www.bilibili.com/read/cv25133736)　　　 [xuniren](https://www.bilibili.com/read/cv24997550)　　　Remote PC



*重要: Fay（サーバー）とデジタルヒューマン（クライアント）間の通信インターフェース： ['ws://127.0.0.1:10002'](ws://127.0.0.1:10002) (connected)*

メッセージフォーマット: [WebSocket.md](https://github.com/TheRamU/Fay/blob/main/WebSocket.md) を見る

![](images/kzq.jpg)



**コード構造**

```
.

├── main.py	            # プログラムのメインエントリ
├── fay_booter.py	    # コアブートモジュール
├── config.json		    # コントローラ設定ファイル
├── system.conf		    # システム設定ファイル
├── ai_module
│   ├── ali_nls.py	        # Aliyun リアルタイムボイス
│   ├── ms_tts_sdk.py       # Microsoft Text-to-Speech
│   ├── nlp_lingju.py       # Lingju ヒューマンマシンインタラクション - 自然言語処理
│   ├── xf_aiui.py          # Xunfei ヒューマンマシンインタラクション - 自然言語処理
│   ├── nlp_gpt.py          # GPT API インテグレーション
│   ├── nlp_chatgpt.py      # chat.openai.com との逆統合
│   ├── nlp_yuan.py         # Langchao. Yuan モデル統合
│   ├── nlp_rasa.py         # ChatGLM-6B ベースの先行 Rasa 会話管理 (強く推奨)
│   ├── nlp_VisualGLM.py    # nlp_VisualGLM.py # マルチモーダル大規模言語モデル VisualGLM-6B との統合
│   ├── nlp_rwkv.py         # rwkv とのオフライン統合
│   ├── nlp_rwkv_api.py     # rwkv サーバー API
│   ├── yolov8.py           # YOLOv8 オブジェクト検出
│   └── xf_ltp.py           # Xunfei 感情分析
├── bin                     # 実行ファイルディレクトリ
├── core                    # デジタルヒューマンコア
│   ├── fay_core.py         # デジタルヒューマンコアモジュール
│   ├── recorder.py         # レコーダー
│   ├── tts_voice.py        # 音声合成の列挙
│   ├── authorize_tb.py     # fay.db 認証テーブルの管理
│   ├── content_db.py       # fay.db コンテンツテーブル管理
│   ├── interact.py         # インタラクション（メッセージ）オブジェクト
│   ├── song_player.py      # 音楽プレイヤー（現在利用不可）
│   └── wsa_server.py       # WebSocket サーバー
├── gui                     # グラフィカルインターフェース
│   ├── flask_server.py     # Flask サーバー
│   ├── static
│   ├── templates
│   └── window.py           # ウィンドウモジュール
├── scheduler
│   └── thread_manager.py   # スケジューラマネージャ
├── utils                   # ユーティリティモジュール
│   ├── config_util.py
│   ├── storer.py
│   └── util.py
└── test                    # 全てのサプライズ

```





## **更新ログ**

**2023.07.28：**

+ UI キャッシュのランタイム自動クリーニングを追加;
+  GPT プロキシの設定をNULLにできるようにした;
+ Lingju ドッキングの安定性を改善。

**2023.07.21：**

+ デジタルヒューマンを接続する前に、大量の WS 情報を生成していた問題を修正;
+  デジタルヒューマン（UE、Live2D、Xuniren）通信インターフェース：リアルタイムログを追加;
+ デジタルヒューマン(UE、Live2D、Xuniren) コミュニケーションインターフェースの更新：オーディオプッシュ。

**2023.07.21：**

+ 製品版版の複数のアップデート。

**2023.07.19：**
+ リモート音声認識の問題を修正しました。
+ ASR (自動音声認識)中に無反応になることがあった問題を修正。
+ 歌唱コマンドを削除しました。

**2023.07.14：**

+ Linux と macOS のランタイムエラーを修正しました。
+ リップシンクのエラーで実行を継続できない問題を修正。
+ RWKV の統合ソリューションを提供。

**2023.07.12：**

+ アシスタントエディションで、テキスト入力がペルソナの回答を読み取れない問題を修正しました。
+ アシスタントエディションで、テキスト入力がQAの回答を読み取らない問題を修正。
+ マイクの安定性が向上しました。

**2023.07.05：**

+ リップシンクアルゴリズムを実行できないことに起因するサウンド再生の問題を修正。

**2023.06：**

+ より簡単な拡張のために、NLP モジュール管理ロジックをリファクタリングしました。
+ GPT を ChatGPT と GPT に分割し、新しい GPT インターフェースに置き換え、プロキシサーバーを個別に設定する機能を追加。
+ YOLO の互換性の問題を解決するために、YOLOv8 パッケージのバージョンを指定しました。
+ 自分語りのバグと、複数のメッセージを受信して処理するバグを修正。
+ Lingju NLP API を統合（GPT3.5 と複数のアプリケーションをサポート）。
+ UI の修正。
+ ローカルリップシンクアルゴリズムを統合。
+ マルチチャンネルマイクとの互換性の問題を解決。
+ fay_core.py と fay_booter.py のリファクタリング。
+ UI レイアウトの調整。
+ サウンド選択を復元。
+ "Thinking..." を表示するロジックを修正。


## **インストール方法**


### **環境**
- Python 3.9、3.10
- Windows、macos、linux

### **依存関係のインストール**

```shell
pip install -r requirements.txt
```

### **アプリケーションキーの設定**
+ [API モジュール](#api-モジュール)を見る
+  リンクをブラウズして登録し、アプリケーションを作成する。`./system.conf` にアプリケーションキーを記入する。

### **Starting**

Starting Fay Controller

```shell
python main.py
```


### **API モジュール**

開始前にアプリケーションキーの記入が必要

| ファイル                        | 説明                                              | リンク                                                         |
|-----------------------------|----------------------------------------------------------|--------------------------------------------------------------|
| ./ai_module/ali_nls.py      | リアルタイム音声認識 (*オプション*) | https://ai.aliyun.com/nls/trans                              |
| ./ai_module/ms_tts_sdk.py   | Microsoft エモーション音声合成 (*オプション*) | https://azure.microsoft.com/zh-cn/services/cognitive-services/text-to-speech/ |
| ./ai_module/xf_ltp.py       | Xunfei 感情分析(*オプション*)                     | https://www.xfyun.cn/service/emotion-analysis                |
| ./utils/ngrok_util.py       | ngrok.cc 外部ネットワーク侵入 (オプション)          | http://ngrok.cc                                              |
| ./ai_module/nlp_lingju.py   | Lingju NLP API (GPT3.5と複数のアプリケーションをサポート)(*オプション*) | https://open.lingju.ai   GPT3.5 へのアクセスを有効にするには、カスタマーサービスにお問い合わせください |
| ./ai_module/yuan_1_0.py     | Langchao Yuan モデル (*オプション*)           | https://air.inspur.com/                                              |


## **使用説明書**


### **使用説明書**

+ 音声アシスタント： Fayコントローラー（マイク入力ソースを有効にし、パネル再生を有効にした場合）。
+ リモート音声アシスタント： フェイ・コントローラー（パネル再生は無効）。
+ デジタルヒューマンインタラクション： Fay コントローラー（マイク入力ソース有効、パネル再生無効、パーソナリティQ&A記入） + デジタルヒューマン。
+ ジャービス、彼女：一緒に体験を完成させましょう。


### **音声コマンド**

| シャットダウン                  | ミュート                       | ミュート解除                                                         |
| ------------------------- | -------------------------- | ------------------------------------------------------------ |
| シャットダウン、グッドバイ、ゴー・アウェイ    | ミュート、静かに、静寂が欲しい        |   ミュート解除, どこにいる, 今すぐ話せる                           |



### **ビジネスに関するお問い合わせ**

**ビジネス QQ **: 467665317





