package com.nathan.chesscamera

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.TextView
import androidx.fragment.app.Fragment
import com.google.android.material.textfield.TextInputEditText
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class SettingsFragment : Fragment(R.layout.fragment_settings) {
    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val ipField = view.findViewById<TextInputEditText>(R.id.ip_field)
        val result = view.findViewById<TextView>(R.id.test_result)
        ipField.setText(Prefs.macIp(requireContext()))

        view.findViewById<View>(R.id.btn_test).setOnClickListener {
            val ip = ipField.text.toString().trim()
            if (ip.isEmpty()) { result.text = "Enter an IP first"; return@setOnClickListener }
            Prefs.setMacIp(requireContext(), ip)
            result.text = "Testing…"
            executor.execute {
                val ok = try {
                    val conn = URL("http://$ip:5001/").openConnection() as HttpURLConnection
                    conn.connectTimeout = 3000
                    conn.readTimeout = 3000
                    conn.responseCode  // any HTTP response (even 404/405) means the server is reachable
                    conn.disconnect()
                    true
                } catch (e: Exception) { false }
                main.post { result.text = if (ok) "✓ Mac reachable" else "✗ Can't reach $ip:5001" }
            }
        }
    }

    override fun onPause() {
        super.onPause()
        view?.findViewById<TextInputEditText>(R.id.ip_field)?.text?.toString()?.trim()
            ?.takeIf { it.isNotEmpty() }?.let { Prefs.setMacIp(requireContext(), it) }
    }

    override fun onDestroy() { super.onDestroy(); executor.shutdown() }
}
