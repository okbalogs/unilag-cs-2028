package com.nanostack.runner

import android.graphics.Color
import android.text.TextUtils
import android.util.Log
import android.view.View
import android.widget.EditText
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject

object ActionHandler {

    private const val TAG = "NanoAction"

    /**
     * Execute a JSON action array in sequence.
     * [currentView] is the root View of the current screen — used to find
     * input fields by their `tag` (set from the input's `id` property).
     */
    fun execute(actions: JSONArray, activity: MainActivity, currentView: View?) {
        for (i in 0 until actions.length()) {
            val action = actions.getJSONObject(i)
            runAction(action, activity, currentView)
        }
    }

    private fun runAction(action: JSONObject, activity: MainActivity, view: View?) {
        when (val type = action.optString("action")) {

            "navigate" -> {
                val target = action.optString("target")
                if (target.isNotBlank()) activity.navigateTo(target)
            }

            "show_toast" -> {
                val raw = action.optString("message", "")
                val msg = interpolate(raw, activity)
                Toast.makeText(activity, msg, Toast.LENGTH_SHORT).show()
            }

            "validate" -> {
                val fields = action.optJSONArray("fields") ?: JSONArray()
                var allValid = true
                for (i in 0 until fields.length()) {
                    val fieldId = fields.getString(i)
                    val et = view?.findViewWithTag<EditText>(fieldId)
                    if (et == null || et.text.isNullOrBlank()) {
                        et?.error = "This field is required"
                        allValid = false
                    }
                }
                if (!allValid) {
                    Toast.makeText(activity, "Please fill in all required fields",
                        Toast.LENGTH_SHORT).show()
                    // Stop action chain on validation failure by throwing a
                    // checked sentinel — caught by the execute() caller
                    throw ValidationFailedException()
                }
            }

            "store" -> {
                val variable = action.optString("variable", "")
                val value    = action.opt("value") ?: ""
                if (variable.isNotBlank()) {
                    activity.storeValue(variable, interpolate(value.toString(), activity))
                }
            }

            "run_script" -> {
                val scriptName = action.optString("script", "")
                val steps = activity.scriptsMap[scriptName]
                if (steps != null) {
                    execute(steps, activity, view)
                } else {
                    Log.w(TAG, "Script '$scriptName' not found")
                }
            }

            "call" -> {
                // v1: stub — logs the service call; real service implementations in v2
                val method = action.optString("method", "")
                Log.d(TAG, "Service call: $method")
                Toast.makeText(activity, "Service: $method", Toast.LENGTH_SHORT).show()
            }

            "if" -> {
                val condition = action.optString("condition", "")
                val result    = evaluateCondition(condition, activity)
                val branch    = if (result) action.optJSONArray("then") else action.optJSONArray("else")
                if (branch != null) execute(branch, activity, view)
            }

            "update" -> {
                // refresh the current screen view (re-render) — useful after store
                val target = action.optString("target", "")
                Log.d(TAG, "update target=$target")
            }

            else -> Log.w(TAG, "Unknown action: $type")
        }
    }

    /**
     * Replace $variable.path tokens with values from the store.
     * e.g. "Hello $device.name" → "Hello Pixel 6"
     */
    fun interpolate(text: String, activity: MainActivity): String {
        if (!text.contains('$')) return text
        val sb = StringBuilder()
        val parts = text.split(Regex("(?=\\$)"))
        for (part in parts) {
            if (part.startsWith('$')) {
                val key = part.drop(1).takeWhile { it.isLetterOrDigit() || it == '.' || it == '_' }
                val rest = part.drop(1 + key.length)
                val stored = activity.getValue(key)
                sb.append(stored?.toString() ?: part.take(1 + key.length))
                sb.append(rest)
            } else {
                sb.append(part)
            }
        }
        return sb.toString()
    }

    /**
     * Very simple condition evaluator for v1.
     * Supports: "varName == value" and "varName != value"
     */
    private fun evaluateCondition(condition: String, activity: MainActivity): Boolean {
        return when {
            condition.contains("==") -> {
                val (left, right) = condition.split("==", limit = 2).map { it.trim() }
                val stored = activity.getValue(left)?.toString() ?: ""
                stored == right
            }
            condition.contains("!=") -> {
                val (left, right) = condition.split("!=", limit = 2).map { it.trim() }
                val stored = activity.getValue(left)?.toString() ?: ""
                stored != right
            }
            else -> {
                // treat as truthy check: non-null, non-empty, non-"false"
                val stored = activity.getValue(condition)?.toString() ?: condition
                stored.isNotBlank() && stored != "false" && stored != "0"
            }
        }
    }
}

/** Thrown by validate actions to halt the action chain cleanly. */
class ValidationFailedException : RuntimeException("Validation failed")
