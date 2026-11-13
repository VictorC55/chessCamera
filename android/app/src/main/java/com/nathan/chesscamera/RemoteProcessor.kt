package com.nathan.chesscamera

import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class RemoteProcessor(private val ip: String) : BoardProcessor {

    companion object { private val executor = Executors.newSingleThreadExecutor() }

    private class Reply(val code: Int, val body: String)

    private fun post(route: String, photo: File, corners: BoardCorners?): Reply {
        val bytes = photo.readBytes()      // original file, EXIF intact
        val boundary = "----ChessCameraBoundary"
        val conn = URL("http://$ip:5001/$route").openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.connectTimeout = 5000
        conn.readTimeout = 30000
        conn.doOutput = true
        conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        conn.outputStream.use {
            if (corners != null) {
                it.write("--$boundary\r\n".toByteArray())
                it.write("Content-Disposition: form-data; name=\"corners\"\r\n\r\n".toByteArray())
                it.write(corners.toJson().toByteArray())
                it.write("\r\n".toByteArray())
            }
            it.write("--$boundary\r\n".toByteArray())
            it.write("Content-Disposition: form-data; name=\"image\"; filename=\"phone_capture.jpg\"\r\n".toByteArray())
            it.write("Content-Type: image/jpeg\r\n\r\n".toByteArray())
            it.write(bytes)
            it.write("\r\n--$boundary--\r\n".toByteArray())
        }
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val body = stream?.bufferedReader()?.use { it.readText() } ?: ""
        conn.disconnect()
        return Reply(code, body)
    }

    override fun detectCorners(photo: File, onResult: (CornerEstimate) -> Unit) {
        executor.execute {
            try {
                val r = post("detect_corners", photo, null)
                if (r.code != 200) {
                    onResult(CornerEstimate(null, "Server error: ${r.code}")); return@execute
                }
                val json = JSONObject(r.body)
                if (!json.optBoolean("ok", false)) {
                    onResult(CornerEstimate(null, "Couldn't find the board")); return@execute
                }
                val c = BoardCorners.fromJson(json.getJSONArray("corners").toString())
                onResult(
                    if (c != null) CornerEstimate(c, "Auto-detected")
                    else CornerEstimate(null, "Bad reply from the Mac")
                )
            } catch (e: Exception) {
                onResult(CornerEstimate(null, "Can't reach the Mac"))
            }
        }
    }

    override fun process(photo: File, corners: BoardCorners?, onResult: (ProcessResult) -> Unit) {
        executor.execute {
            try {
                val r = post("upload", photo, corners)
                onResult(
                    if (r.code == 200) ProcessResult(true, "Sent to Mac ✓")
                    else ProcessResult(false, "Server error: ${r.code}")
                )
            } catch (e: Exception) {
                onResult(ProcessResult(false, "Failed: ${e.message}"))
            }
        }
    }
}
