package com.nathan.chesscamera

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class RecordFragment : Fragment(R.layout.fragment_record) {
    private lateinit var previewView: PreviewView
    private lateinit var status: TextView
    private var imageCapture: ImageCapture? = null
    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    private val requestPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera() else setStatus("Camera permission denied")
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        previewView = view.findViewById(R.id.preview)
        status = view.findViewById(R.id.status_pill)
        view.findViewById<View>(R.id.shutter).setOnClickListener { captureAndSend() }

        val granted = ContextCompat.checkSelfPermission(
            requireContext(), Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED
        if (granted) startCamera() else requestPermission.launch(Manifest.permission.CAMERA)
    }

    private fun setStatus(text: String) {
        main.post { if (isAdded) status.text = text }
    }

    private fun startCamera() {
        val ctx = requireContext()
        val providerFuture = ProcessCameraProvider.getInstance(ctx)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }
            imageCapture = ImageCapture.Builder().build()
            try {
                provider.unbindAll()
                provider.bindToLifecycle(
                    viewLifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageCapture
                )
            } catch (e: Exception) {
                setStatus("Camera start failed: ${e.message}")
            }
        }, ContextCompat.getMainExecutor(ctx))
    }

    private fun captureAndSend() {
        val capture = imageCapture ?: return
        val ctx = requireContext().applicationContext
        val ip = Prefs.macIp(ctx)
        if (ip.isBlank()) { setStatus("Set the Mac IP in Settings"); return }

        val photoFile = File(ctx.externalCacheDir, "temp_photo.jpg")
        capture.takePicture(
            ImageCapture.OutputFileOptions.Builder(photoFile).build(),
            ContextCompat.getMainExecutor(ctx),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                    setStatus("Sending…")
                    sendToMac(photoFile, ip)
                }
                override fun onError(e: ImageCaptureException) {
                    setStatus("Capture failed")
                }
            }
        )
    }

    private fun sendToMac(file: File, ip: String) {
        executor.execute {
            try {
                val bitmap = BitmapFactory.decodeFile(file.absolutePath)
                val out = ByteArrayOutputStream()
                bitmap.compress(Bitmap.CompressFormat.JPEG, 90, out)
                val bytes = out.toByteArray()

                val conn = URL("http://$ip:5001/upload").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.connectTimeout = 5000
                conn.readTimeout = 15000
                conn.doOutput = true
                val boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
                conn.outputStream.use {
                    it.write("--$boundary\r\n".toByteArray())
                    it.write("Content-Disposition: form-data; name=\"image\"; filename=\"phone_capture.jpg\"\r\n".toByteArray())
                    it.write("Content-Type: image/jpeg\r\n\r\n".toByteArray())
                    it.write(bytes)
                    it.write("\r\n--$boundary--\r\n".toByteArray())
                }
                val code = conn.responseCode
                setStatus(if (code == 200) "Sent to Mac ✓" else "Server error: $code")
            } catch (e: Exception) {
                setStatus("Failed: ${e.message}")
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        executor.shutdown()
    }
}