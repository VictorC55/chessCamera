package com.nathan.chesscamera

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Bundle
import android.view.ViewGroup
import android.widget.Button
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

    // Updated to your Mac's IP Address
    private val macIpAddress = "172.20.10.2"

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

        val photoFile = File(externalCacheDir, "temp_photo.jpg")
        val outputOptions = ImageCapture.OutputFileOptions.Builder(photoFile).build()

        imageCapture.takePicture(
            outputOptions,
            ContextCompat.getMainExecutor(this),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                    Toast.makeText(this@MainActivity, "Sending...", Toast.LENGTH_SHORT).show()
                    sendToMac(photoFile)
                }
                override fun onError(exception: ImageCaptureException) {
                    Toast.makeText(this@MainActivity, "Capture failed", Toast.LENGTH_SHORT).show()
                }
            }
        )
    }

    private fun sendToMac(file: File) {
        executor.execute {
            try {
                val bitmap = BitmapFactory.decodeFile(file.absolutePath)
                val outputStream = ByteArrayOutputStream()
                bitmap.compress(Bitmap.CompressFormat.JPEG, 90, outputStream)
                val imageBytes = outputStream.toByteArray()

                val url = URL("http://$macIpAddress:5001/upload")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
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