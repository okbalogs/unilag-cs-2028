package com.nanostack.runner

import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject

object ScreenRenderer {

    /**
     * Build and return the complete View tree for a screen JSONObject.
     * The returned view is a ScrollView containing a vertical LinearLayout
     * with all components stacked top-to-bottom.
     */
    fun render(screen: JSONObject, activity: MainActivity): View {
        val scroll = ScrollView(activity).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        val container = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
            setPadding(dp(activity, 16), dp(activity, 16),
                dp(activity, 16), dp(activity, 32))
        }

        // Background colour
        val bg = screen.optString("background", "#FFFFFF")
        try { scroll.setBackgroundColor(Color.parseColor(bg)) }
        catch (_: Exception) { scroll.setBackgroundColor(Color.WHITE) }

        // Render each component
        val components = screen.optJSONArray("components") ?: JSONArray()
        for (i in 0 until components.length()) {
            val comp = components.getJSONObject(i)
            val view = buildComponent(comp, activity, container)
            if (view != null) {
                container.addView(view)
                addVerticalSpacing(activity, container, 12)
            }
        }

        scroll.addView(container)
        return scroll
    }

    // ── Component builders ────────────────────────────────────────────────────

    private fun buildComponent(
        comp: JSONObject,
        activity: MainActivity,
        parent: LinearLayout,
    ): View? {
        return when (comp.optString("type")) {
            "text"   -> buildText(comp, activity)
            "input"  -> buildInput(comp, activity)
            "button" -> buildButton(comp, activity, parent)
            "link"   -> buildLink(comp, activity, parent)
            "image"  -> buildImage(comp, activity)
            "list"   -> buildList(comp, activity, parent)
            else     -> null
        }
    }

    // ── text ──────────────────────────────────────────────────────────────────

    private fun buildText(comp: JSONObject, activity: MainActivity): TextView {
        return TextView(activity).apply {
            text = ActionHandler.interpolate(comp.optString("value", ""), activity)

            val sizeSp = comp.optDouble("size", 16.0).toFloat()
            setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)

            val bold   = comp.optBoolean("bold", false)
            val italic = comp.optBoolean("italic", false)
            typeface = when {
                bold && italic -> Typeface.create(Typeface.DEFAULT, Typeface.BOLD_ITALIC)
                bold           -> Typeface.DEFAULT_BOLD
                italic         -> Typeface.create(Typeface.DEFAULT, Typeface.ITALIC)
                else           -> Typeface.DEFAULT
            }

            val colour = comp.optString("color", "#111111")
            try { setTextColor(Color.parseColor(colour)) }
            catch (_: Exception) { setTextColor(Color.BLACK) }

            gravity = when (comp.optString("align", "left")) {
                "center" -> Gravity.CENTER_HORIZONTAL
                "right"  -> Gravity.END
                else     -> Gravity.START
            }

            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        }
    }

    // ── input ─────────────────────────────────────────────────────────────────

    private fun buildInput(comp: JSONObject, activity: MainActivity): EditText {
        return EditText(activity).apply {
            hint = comp.optString("hint", "")
            tag  = comp.optString("id", "")

            inputType = when (comp.optString("input_type", "text")) {
                "email"    -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
                "password" -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
                "number"   -> InputType.TYPE_CLASS_NUMBER
                "phone"    -> InputType.TYPE_CLASS_PHONE
                else       -> InputType.TYPE_CLASS_TEXT
            }

            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            setPadding(dp(activity, 8), dp(activity, 12),
                dp(activity, 8), dp(activity, 12))
        }
    }

    // ── button ────────────────────────────────────────────────────────────────

    private fun buildButton(
        comp: JSONObject,
        activity: MainActivity,
        parent: LinearLayout,
    ): Button {
        return Button(activity).apply {
            text = comp.optString("label", "Button")

            val colour = comp.optString("color", "#4A90E2")
            try { setBackgroundColor(Color.parseColor(colour)) }
            catch (_: Exception) { setBackgroundColor(Color.parseColor("#4A90E2")) }
            setTextColor(Color.WHITE)

            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )

            val actions = comp.optJSONArray("on_click") ?: JSONArray()
            setOnClickListener {
                try {
                    // Find the root scroll view (grandparent of parent)
                    val screenRoot: View? = (parent.parent as? View)?.let {
                        if (it is ScrollView) it else parent
                    }
                    ActionHandler.execute(actions, activity, screenRoot ?: parent)
                } catch (_: ValidationFailedException) {
                    // Validation failure already showed error — just stop
                }
            }
        }
    }

    // ── link ──────────────────────────────────────────────────────────────────

    private fun buildLink(
        comp: JSONObject,
        activity: MainActivity,
        parent: LinearLayout,
    ): TextView {
        return TextView(activity).apply {
            text = comp.optString("label", "")
            setTextColor(Color.parseColor("#4A90E2"))
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(0, dp(activity, 4), 0, dp(activity, 4))

            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )

            val navTarget = comp.optString("navigate", "")
            if (navTarget.isNotBlank()) {
                setOnClickListener { activity.navigateTo(navTarget) }
            }
        }
    }

    // ── image ─────────────────────────────────────────────────────────────────

    private fun buildImage(comp: JSONObject, activity: MainActivity): View {
        // v1: render a grey placeholder box showing the source path/variable
        val source = ActionHandler.interpolate(comp.optString("source", ""), activity)
        val heightDp = comp.optDouble("height", 200.0).toInt()

        return TextView(activity).apply {
            text = "[ Image: $source ]"
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#CCCCCC"))
            setTextColor(Color.parseColor("#555555"))
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(activity, heightDp)
            )
        }
    }

    // ── list ──────────────────────────────────────────────────────────────────

    private fun buildList(
        comp: JSONObject,
        activity: MainActivity,
        parent: LinearLayout,
    ): LinearLayout {
        val listContainer = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        }

        val sourceKey = comp.optString("source", "")
        val storedData = activity.getValue(sourceKey)
        val template   = comp.optJSONObject("item_template")
        val emptyText  = comp.optString("empty_text", "No items")

        if (storedData == null) {
            // Show empty state
            listContainer.addView(TextView(activity).apply {
                text = emptyText
                setTextColor(Color.GRAY)
                gravity = Gravity.CENTER_HORIZONTAL
                setPadding(0, dp(activity, 16), 0, dp(activity, 16))
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )
            })
            return listContainer
        }

        // Render item rows from stored JSONArray
        val items = when (storedData) {
            is org.json.JSONArray -> storedData
            is String -> try { org.json.JSONArray(storedData) } catch (_: Exception) { null }
            else -> null
        }

        if (items == null || items.length() == 0) {
            listContainer.addView(TextView(activity).apply {
                text = emptyText
                setTextColor(Color.GRAY)
                gravity = Gravity.CENTER_HORIZONTAL
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )
            })
            return listContainer
        }

        for (i in 0 until items.length()) {
            val item = items.optJSONObject(i) ?: continue
            val row  = buildListRow(item, template, activity, parent)
            listContainer.addView(row)
            addVerticalSpacing(activity, listContainer, 4)
        }

        return listContainer
    }

    private fun buildListRow(
        item: JSONObject,
        template: JSONObject?,
        activity: MainActivity,
        parent: LinearLayout,
    ): LinearLayout {
        val row = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(activity, 8), dp(activity, 12),
                dp(activity, 8), dp(activity, 12))
            setBackgroundColor(Color.parseColor("#F5F5F5"))
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        }

        val textCol = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }

        // Main text
        val mainText = template?.optString("text", "")?.let {
            interpolateItemField(it, item)
        } ?: item.optString("name", item.toString())

        textCol.addView(TextView(activity).apply {
            text = mainText
            setTextColor(Color.parseColor("#111111"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        })

        // Subtext
        val subText = template?.optString("subtext", "")?.let {
            interpolateItemField(it, item)
        } ?: ""
        if (subText.isNotBlank()) {
            textCol.addView(TextView(activity).apply {
                text = subText
                setTextColor(Color.GRAY)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            })
        }

        row.addView(textCol)

        // on_tap handler on the whole row
        val tapActions = template?.optJSONArray("on_tap") ?: JSONArray()
        if (tapActions.length() > 0) {
            row.setOnClickListener {
                activity.storeValue("tapped_device", item.toString())
                try {
                    ActionHandler.execute(tapActions, activity, parent)
                } catch (_: ValidationFailedException) { }
            }
        }

        return row
    }

    // ── helpers ───────────────────────────────────────────────────────────────

    private fun interpolateItemField(template: String, item: JSONObject): String {
        if (!template.contains('$')) return template
        var result = template
        val keys = template.split(Regex("\\$"))
            .drop(1)
            .map { it.takeWhile { c -> c.isLetterOrDigit() || c == '.' || c == '_' } }
        for (key in keys) {
            val parts = key.split(".", limit = 2)
            val value = if (parts.size == 2) item.optString(parts[1], "") else item.optString(key, "")
            result = result.replace("\$$key", value)
        }
        return result
    }

    private fun addVerticalSpacing(context: Context, parent: LinearLayout, dp: Int) {
        parent.addView(View(context).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(context, dp)
            )
        })
    }

    private fun dp(context: Context, value: Int): Int =
        (value * context.resources.displayMetrics.density).toInt()
}
