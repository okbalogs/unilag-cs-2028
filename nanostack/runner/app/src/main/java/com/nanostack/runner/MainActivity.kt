package com.nanostack.runner

import android.os.Bundle
import android.util.Log
import android.view.KeyEvent
import android.widget.FrameLayout
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "NanoRunner"
    }

    // Parsed top-level logic.json payload
    lateinit var appData: JSONObject
    lateinit var screensMap: Map<String, JSONObject>
    lateinit var scriptsMap: Map<String, JSONArray>

    // Runtime state
    private val navStack = mutableListOf<String>()
    private val store = HashMap<String, Any>()
    private lateinit var container: FrameLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        container = findViewById(R.id.screen_container)

        try {
            val json = loadLogicJson()
            appData = json

            // Index screens and scripts by name for O(1) lookup
            screensMap = buildScreensMap(json.getJSONArray("screens"))
            scriptsMap = buildScriptsMap(json.optJSONArray("scripts"))

            // Navigate to the entry screen
            val entryScreen = json.getJSONObject("app").getString("entry_screen")
            navigateTo(entryScreen)

        } catch (e: Exception) {
            Log.e(TAG, "Failed to load logic.json", e)
            Toast.makeText(this, "Error: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    // ── Navigation ────────────────────────────────────────────────────────────

    fun navigateTo(screenName: String) {
        val screen = screensMap[screenName]
        if (screen == null) {
            Log.e(TAG, "Screen '$screenName' not found")
            Toast.makeText(this, "Screen '$screenName' not found", Toast.LENGTH_SHORT).show()
            return
        }
        navStack.add(screenName)
        renderScreen(screen)
    }

    fun goBack(): Boolean {
        if (navStack.size <= 1) return false
        navStack.removeAt(navStack.lastIndex)
        val prev = navStack.last()
        screensMap[prev]?.let { renderScreen(it) }
        return true
    }

    private fun renderScreen(screen: JSONObject) {
        container.removeAllViews()
        val view = ScreenRenderer.render(screen, this)
        container.addView(view)
    }

    // ── Back button ───────────────────────────────────────────────────────────

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (goBack()) return true
        }
        return super.onKeyDown(keyCode, event)
    }

    // ── Store ─────────────────────────────────────────────────────────────────

    fun storeValue(key: String, value: Any) {
        store[key] = value
    }

    fun getValue(key: String): Any? = store[key]

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun loadLogicJson(): JSONObject {
        val text = assets.open("logic.json").bufferedReader().readText()
        return JSONObject(text)
    }

    private fun buildScreensMap(arr: JSONArray): Map<String, JSONObject> {
        val map = LinkedHashMap<String, JSONObject>()
        for (i in 0 until arr.length()) {
            val s = arr.getJSONObject(i)
            map[s.getString("name")] = s
        }
        return map
    }

    private fun buildScriptsMap(arr: JSONArray?): Map<String, JSONArray> {
        if (arr == null) return emptyMap()
        val map = HashMap<String, JSONArray>()
        for (i in 0 until arr.length()) {
            val s = arr.getJSONObject(i)
            map[s.getString("name")] = s.getJSONArray("steps")
        }
        return map
    }
}
