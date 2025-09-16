import threading
import webbrowser
from flask import Flask
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.utils import platform

# Import your existing Flask app (app.py)
from app import app as flask_app  

# Function to run Flask in a separate thread
def run_flask():
    flask_app.run(host='0.0.0.0', port=5000)

class MainApp(App):
    def build(self):
        layout = BoxLayout(orientation='vertical')
        label = Label(text="Starting Healthcare App...", font_size='20sp')
        open_button = Button(text="Open App", size_hint=(1, 0.2))
        open_button.bind(on_press=self.open_browser)
        layout.add_widget(label)
        layout.add_widget(open_button)

        # Start Flask server in another thread
        threading.Thread(target=run_flask, daemon=True).start()

        return layout

    def open_browser(self, instance):
        url = "http://127.0.0.1:5000"
        if platform == 'android':
            import android
            android.webview.launch(url)
        else:
            webbrowser.open(url)

if __name__ == "__main__":
    MainApp().run()
