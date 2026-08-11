import subprocess


def _escape(text: str) -> str:
    return (text or "").replace('"', "'").replace("`", "'").replace("$", "")


def send_windows_toast(title: str, message: str):
    safe_title = _escape(title)
    safe_message = _escape(message)

    ps_script = f'''
$ErrorActionPreference = "SilentlyContinue"
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName("text")
$textNodes.Item(0).AppendChild($template.CreateTextNode("{safe_title}")) | Out-Null
$textNodes.Item(1).AppendChild($template.CreateTextNode("{safe_message}")) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Piramit Muhasebe").Show($toast)
'''
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"[notifier] Toast gönderilemedi: {e}")
