# SPEC.md — システム仕様書

## 現行ツール仕様

### tour_reply_generator_app.py（Streamlit版）

#### 入力パラメータ

| パラメータ | 型 | 選択肢 | 説明 |
|---|---|---|---|
| 返信タイプ | selectbox | AGT / EXO / BtoC | 相手先区分 |
| 人数 | number_input | 1以上の整数 | ツアー参加人数 |
| タイプ | selectbox | G / PV | グループ/プライベート（EXO時は非表示） |
| 言語 | selectbox | JP / EN | 返信メールの言語 |
| ツアー | selectbox | ツアーリスト | 対象ツアー |
| メール本文 | text_area | 自由入力 | 受信メールを貼り付け |

#### 料金計算ロジック

```
【AGT / BtoC】
subtotal = 税抜単価 × 人数 + (10,000 if PV else 0)
total = round(subtotal × 1.1)

【EXO】
total = 税込単価 × 人数 (または 1台 if perVehicle)
```

#### 出力

- 返信メール本文（Markdownコードブロック表示）
- 料金内訳（st.info で表示）

#### 返信テンプレート区分

| モード | 言語 | テンプレート |
|---|---|---|
| BtoC | EN固定 | 受付確認・Square決済案内 |
| AGT | JP | 受付確認・PDF1ヶ月前送付案内（日本語署名） |
| AGT | EN | 受付確認・PDF1ヶ月前送付案内（英語フル署名） |
| EXO | JP/EN | 上記AGTと同じロジックで計算式のみ変わる |

---

## ツアーリスト仕様

### AGT / BtoC 共通ツアー（税抜単価）

| キー | ツアー名 | 税抜単価 |
|---|---|---|
| hungry | Hungry Samurai: Sendai Food & Culture Day Tour (with cab) | 30,000円 |
| barhop_sendai | Back-alley Night Izakaya Hopping in Sendai | 20,000円 |
| barhop_sendai_veg | Bar Hopping in Kokubuncho VEG (Sendai) | 20,000円 |
| culinary | Foodie Delight: Culinary Walking Tour (150 min) | 15,000円 |
| shiogama10 | Shiogama's 10 Tasting Treasures | 24,000円 |
| delicacy | Shiogama's Delicacy Trail to Matsushima's Natural Wonders | 35,000円 |
| oyster_jrtrain | Oyster Fisherman's Cruise & Seasonal Feast (JR train) | 32,000円 |
| oyster_matsushima | Cruise with Oyster Fisherman + All-you-can-eat Oyster, Matsushima | 40,000円 |
| fish_feast | Fish & Feast with Local Fisherman! Fishing, Local Traditions, and BBQ Lunch | 32,000円 |
| barhop_hachinohe | Nightlife & Tradition: Hachinohe Yokocho Izakaya Experience (Aomori) | 20,000円 |
| barhop_miyako | Back-alley Bar Hopping in Miyako (Iwate) | 20,000円 |
| barhop_tsuruoka | Bar Hopping in Tsuruoka (Yamagata) | 20,000円 |
| barhop_dake | Dake Onsen Bar Hopping Tour (Fukushima) | 20,000円 |
| barhop_kakunodate | Izakaya and Japanese 'Snack Bar' Tour in Kakunodate (Akita) | 20,000円 |
| attracxi_dewa | Attracxi: Mysteries of the Three Holy Mountains of Dewa | 90,000円（スライド） |
| attracxi_hiraizumi | Attracxi: Hiraizumi Full Day Tour from Sendai | 90,000円（スライド） |
| attracxi_samurai | Attracxi: Master the Way of the Samurai | 90,000円（スライド） |
| attracxi_shiogama_matsushima | Attracxi: Shiogama's Delicacy Trail to Matsushima's Natural Wonders | 90,000円（スライド） |
| attracxi_cask | Attracxi: From Cask to Glass – Tohoku's Craft Journey with Local Cuisine | 90,000円（スライド） |
| attracxi_naruko | Attracxi: Step into Tradition – Craft, Culture, and Hot Springs in Naruko | 90,000円（スライド） |

### EXO専用ツアー（税込単価）

| キー | ツアー名 | 税込単価 | 備考 |
|---|---|---|---|
| barhop_exo | Sendai Bar Hopping Tour (EXO) | 25,960円 | |
| hungry_samurai_fd | Hungry Samurai: Sendai Food & Culture Day Tour (EXO) | 38,500円 | |
| matsushima_shiogama_fd | Matsushima & Shiogama Full Day Tour (EXO) | 41,800円 | |
| hiraizumi | Hiraizumi Full Day Tour from Sendai (EXO) | 89,650円 | |
| hirosaki_hd | HD Tour of Hirosaki (EXO) | 25,000円 | |
| hirosaki_aomori_fd | Hirosaki & Aomori Full Day Tour (EXO) | 35,000円 | |
| dewa_sanzan_sendai | The Sacred Peaks of Yamagata Day Trip from Sendai (EXO) | 要確認 | スライド型の可能性あり |
| private_transfer | Oneway Private Transfer: Sendai → Matsushima (EXO) | 19,800円 | 1台あたり |
| private_transfer_hiace | Oneway Private Transfer: Sendai → Matsushima (Hiace, EXO) | 26,400円 | 1台あたり |

---

## 今後実装予定の機能仕様

### Gmail自動検出
- Gmail APIを使って予約依頼メールを自動取得
- 件名・本文からツアー名・日付・人数を抽出（NLP or 正規表現）

### コンファメーションPDF自動生成
- テンプレートPDFにデータを差し込み出力
- 必須項目：ツアー名・日付・人数・ガイド名・集合場所・料金

### ガイド依頼書の自動作成
- Google Docs APIでテンプレートからドキュメント生成
- 各ガイドの担当ツアー情報を自動入力

### スプレッドシート自動入力
- Google Sheets APIで予約情報を自動追記
- 対象：ツアー管理SS・ガイドアサイン表SS
