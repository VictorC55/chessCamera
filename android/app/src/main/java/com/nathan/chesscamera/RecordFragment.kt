package com.nathan.chesscamera

import android.Manifest
import android.content.pm.PackageManager
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
import java.io.File

class RecordFragment : Fragment(R.layout.fragment_record) {
    private lateinit var previewView: PreviewView
    private lateinit var status: TextView
    private var imageCapture: ImageCapture? = null
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
        view.findViewById<View>(R.id.btn_setup).setOnClickListener { takeSetupPhoto() }

        parentFragmentManager.setFragmentResultListener(
            CornerSetupDialog.RESULT_KEY, viewLifecycleOwner
        ) { _, b ->
            if (b.getBoolean("confirmed")) setStatus("Board set ✓")
            else if (b.getBoolean("retake")) setStatus("Reframe the board, then tap Set up board")
        }

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
        if (!Prefs.useLocal(ctx)) {
            val ip = Prefs.macIp(ctx)
            if (ip.isBlank()) { setStatus("Set the Mac IP in Settings"); return }
        }

        val photoFile = File(ctx.externalCacheDir, "temp_photo.jpg")
        capture.takePicture(
            ImageCapture.OutputFileOptions.Builder(photoFile).build(),
            ContextCompat.getMainExecutor(ctx),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                    setStatus("Sending…")
                    Processors.get(ctx).process(photoFile, Prefs.corners(ctx)) { r -> setStatus(r.message) }
                }
                override fun onError(e: ImageCaptureException) {
                    setStatus("Capture failed")
                }
            }
        )
    }

    private fun takeSetupPhoto() {
        val capture = imageCapture ?: return
        val ctx = requireContext()
        val file = File(ctx.cacheDir, "setup_photo.jpg")
        capture.takePicture(
            ImageCapture.OutputFileOptions.Builder(file).build(),
            ContextCompat.getMainExecutor(ctx),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(o: ImageCapture.OutputFileResults) {
                    if (!isAdded) return
                    CornerSetupDialog.newInstance(file.absolutePath)
                        .show(parentFragmentManager, "corner_setup")
                }
                override fun onError(e: ImageCaptureException) {
                    setStatus("Capture failed")
                }
            }
        )
    }

    override fun onDestroy() {
        super.onDestroy()
    }
}