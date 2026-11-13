package com.nathan.chesscamera

import android.graphics.PointF
import org.json.JSONArray

/** Normalized (0..1) image coordinates, upright image, order: a8, h8, h1, a1. */
data class BoardCorners(val pts: List<PointF>) {
    fun toJson(): String {
        val arr = JSONArray()
        pts.forEach { arr.put(JSONArray().put(it.x.toDouble()).put(it.y.toDouble())) }
        return arr.toString()
    }

    companion object {
        fun fromJson(s: String): BoardCorners? = try {
            val arr = JSONArray(s)
            if (arr.length() != 4) null
            else BoardCorners(List(4) { i ->
                val p = arr.getJSONArray(i)
                PointF(p.getDouble(0).toFloat(), p.getDouble(1).toFloat())
            })
        } catch (e: Exception) { null }
    }
}
