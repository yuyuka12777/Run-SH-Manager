# Run SH Manager

Linux (Ubuntu) 向けにシェルスクリプトを安全に常駐管理するための GUI アプリケーションです。複数のシェルスクリプト (例: 複数の Minecraft サーバー) を 1 つの画面で監視・起動・再起動できます。

## 必要環境

- Ubuntu 22.04 / Linux Mint 21 以降 (他の Debian 系でも動作見込み)
- Python 3.10 以上 (`python3 --version` で確認)
- X11 フォワーディング (MobaXterm, VS Code Remote 等で GUI を表示する場合)
- `python3-pip` 

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv build-essential
```

### deb のインストール

```bash
cd dist
sudo apt install ./run-sh-manager_0.1.0_all.deb
```

インストール後はアプリメニューから「Run SH Manager」が起動できるほか、ターミナルから `run-sh-manager` でも起動できます。

### 再インストール

`sudo apt install ./dist/run-sh-manager_0.1.0_all.deb` を実行すると上書きインストールされます。アンインストールは `sudo apt remove run-sh-manager` です。

## 使い方

1. `run-sh-manager` を起動すると GUI が開きます。
2. ツールバーの「追加」から新しいプロファイルを作成します。
   - **名前**: 表示名 (例: `mc-server-1`)
   - **スクリプトパス**: `/opt/servers/start_mc1.sh` など
   - **作業ディレクトリ**: スクリプト内で相対パスを使う場合に指定
   - **ログファイル**: 空欄の場合は自動生成
   - **再起動待機**: 再起動までの待機秒数
   - **起動遅延**: アプリ起動直後に順次起動したい場合に利用
   - **環境変数**: `KEY=value` 形式で複数行入力
3. 追加後、行を選択して「起動」を押すと監視が開始されます。状態列で `running` と表示されれば成功です。
4. プロファイルの `アプリ起動時に自動起動` を ON にすれば、次回 GUI 起動時に自動で立ち上がります。
5. ツールバーの「ログイン時にアプリを起動」を押すと `~/.config/autostart/run-sh-manager.desktop` が生成され、デスクトップログインと同時に GUI が立ち上がります。
6. GUI を終了すると監視スレッドは停止します。ウィンドウを閉じる際に、実行中のスクリプトを停止するか確認ダイアログを表示します。

### Minecraft サーバーを複数起動する例

1. `/opt/minecraft/server1/start.sh`, `/opt/minecraft/server2/start.sh` などを用意
2. 各サーバー用にプロファイルを作成し、`自動起動` を有効化
3. GUI 起動直後に複数サーバーが順次起動し、異常終了しても指定秒数後に自動復帰
4. リソース使用量表示で各サーバーの負荷を確認

## オプション

- **systemd サービス化 (任意)**: GUI を使わずバックグラウンドで常駐させたい場合は、以下の最小例を `/etc/systemd/system/run-sh-manager.service` に配置して有効化してください。

  ```ini
  [Unit]
  Description=Run SH Manager GUI launcher
  After=network.target

  [Service]
  Type=simple
  ExecStart=/usr/bin/run-sh-manager
  Restart=on-failure
  User=<YOUR_USER>
  Environment=DISPLAY=:0

  [Install]
  WantedBy=default.target
  ```

  `User` や `DISPLAY` は環境に合わせて調整してください。
- **ログローテーション**: 出力ログは `~/.local/share/run_sh_manager/logs` に保存されます。`logrotate` と連携させる場合は同ディレクトリをターゲットに設定してください。

## トラブルシュート

- **GUI が起動しない / `DISPLAY` エラー**: SSH 経由の場合は `ssh -X` でログインするか、X11 フォワーディングを有効化してください。
- **スクリプトがすぐ停止する**: スクリプトに実行権限があるか (`chmod +x script.sh`)、または `/bin/bash script.sh` で直接実行できるか確認します。
- **ログに出力が来ない**: プロファイル編集画面でログパスを確認し、権限と空き容量をチェックしてください。
