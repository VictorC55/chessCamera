package com.nathan.chesscamera

import android.content.Context
import android.os.Build

object Prefs {
    private fun prefs(ctx: Context) = ctx.getSharedPreferences("settings", Context.MODE_PRIVATE)

    private val isEmulator = Build.HARDWARE in setOf("ranchu", "goldfish") ||
            Build.FINGERPRINT.contains("generic")

    private val defaultMacIp get() = if (isEmulator) "10.0.2.2" else BuildConfig.MAC_IP

    fun macIp(ctx: Context): String = prefs(ctx).getString("macIp", defaultMacIp) ?: defaultMacIp

    fun setMacIp(ctx: Context, ip: String) = prefs(ctx).edit().putString("macIp", ip).apply()
}
