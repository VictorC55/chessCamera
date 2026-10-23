package com.nathan.chesscamera

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var previewView: PreviewView
    private lateinit var imageCapture: ImageCapture
    private val executor = Executors.newSingleThreadExecutor()

    private lateinit var ipField: EditText

    // The emulator reaches the Mac it runs on at 10.0.2.2; a real phone defaults to macIp from android/local.properties.
    // Whatever is typed in the IP field is saved on the phone and overrides the default.
    private val isEmulator = Build.HARDWARE in setOf("ranchu", "goldfish") || Build.FINGERPRINT.contains("generic")
    private val defaultMacIp = if (isEmulator) "10.0.2.2" else BuildConfig.MAC_IP
    private val prefs by lazy { getSharedPreferences("settings", MODE_PRIVATE) }

    private val requestPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera()
        else Toast.makeText(this, "Camera permission denied", Toast.LENGTH_SHORT).show()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val layout = FrameLayout(this)
        previewView = PreviewView(this)
        layout.addView(previewView)

        ipField = EditText(this).apply {
            hint = "Mac IP, e.g. 192.168.1.20"
            setText(prefs.getString("macIp", defaultMacIp))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            isSingleLine = true
            setBackgroundColor(0xCCFFFFFF.toInt())
            setPadding(32, 24, 32, 24)
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = android.view.Gravity.TOP
                topMargin = 150
                leftMargin = 48
                rightMargin = 48
            }
        }
        layout.addView(ipField)

        val captureButton = Button(this).apply {
            text = "Send to Mac"
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = android.view.Gravity.BOTTOM or android.view.Gravity.CENTER_HORIZONTAL
                bottomMargin = 100
            }
            setOnClickListener { captureAndSend() }
        }
        layout.addView(captureButton)

        setContentView(layout)

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            requestPermission.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }
            imageCapture = ImageCapture.Builder().build()
            val selector = CameraSelector.DEFAULT_BACK_CAMERA
            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(this, selector, preview, imageCapture)
            } catch (e: Exception) {
                Toast.makeText(this, "Camera start failed: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun captureAndSend() {
        if (!::imageCapture.isInitialized) return
        val macIpAddress = ipField.text.toString().trim()
        if (macIpAddress.isEmpty()) {
            Toast.makeText(this, "Enter the Mac's IP address at the top", Toast.LENGTH_LONG).show()
            return
        }
        prefs.edit().putString("macIp", macIpAddress).apply()

        val photoFile = File(externalCacheDir, "temp_photo.jpg")
        val outputOptions = ImageCapture.OutputFileOptions.Builder(photoFile).build()

        imageCapture.takePicture(
            outputOptions,
            ContextCompat.getMainExecutor(this),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                    Toast.makeText(this@MainActivity, "Sending...", Toast.LENGTH_SHORT).show()
                    sendToMac(photoFile, macIpAddress)
                }
                override fun onError(exception: ImageCaptureException) {
                    Toast.makeText(this@MainActivity, "Capture failed", Toast.LENGTH_SHORT).show()
                }
            }
        )
    }

    private fun sendToMac(file: File, macIpAddress: String) {
        executor.execute {
            try {
                val bitmap = BitmapFactory.decodeFile(file.absolutePath)
                val outputStream = ByteArrayOutputStream()
                bitmap.compress(Bitmap.CompressFormat.JPEG, 90, outputStream)
                val imageBytes = outputStream.toByteArray()

                val url = URL("http://$macIpAddress:5001/upload")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                // Fail fast if the IP is wrong or the Mac isn't reachable, instead of hanging for minutes
                conn.connectTimeout = 5000
                conn.readTimeout = 15000
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW")

                val outputStreamConn = conn.outputStream
                outputStreamConn.write("------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n".toByteArray())
                outputStreamConn.write("Content-Disposition: form-data; name=\"image\"; filename=\"phone_capture.jpg\"\r\n".toByteArray())
                outputStreamConn.write("Content-Type: image/jpeg\r\n\r\n".toByteArray())
                outputStreamConn.write(imageBytes)
                outputStreamConn.write("\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW--\r\n".toByteArray())
                outputStreamConn.close()

                val responseCode = conn.responseCode
                runOnUiThread {
                    if (responseCode == 200) {
                        Toast.makeText(this@MainActivity, "Sent to Mac!", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(this@MainActivity, "Server error: $responseCode", Toast.LENGTH_LONG).show()
                    }
                }
            } catch (e: Exception) {
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "Failed: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }
}