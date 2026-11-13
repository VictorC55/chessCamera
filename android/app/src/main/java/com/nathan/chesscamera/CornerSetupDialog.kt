package com.nathan.chesscamera

import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.fragment.app.DialogFragment
import java.io.File

class CornerSetupDialog : DialogFragment(R.layout.dialog_corner_setup) {

    companion object {
        const val RESULT_KEY = "corner_setup"
        private const val ARG_PATH = "path"
        fun newInstance(path: String) = CornerSetupDialog().apply {
            arguments = Bundle().apply { putString(ARG_PATH, path) }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setStyle(STYLE_NO_FRAME, R.style.Theme_ChessCameraApp)
    }

    override fun onStart() {
        super.onStart()
        dialog?.window?.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
    }

    private fun runDetect(view: View, editor: CornerEditorView, path: String) {
        val status = view.findViewById<TextView>(R.id.tv_status)
        val progress = view.findViewById<View>(R.id.progress)
        progress.visibility = View.VISIBLE
        status.text = "Detecting board…"

        Processors.get(requireContext().applicationContext).detectCorners(File(path)) { est ->
            view.post {
                if (!isAdded) return@post
                progress.visibility = View.GONE
                val c = est.corners
                if (c == null) {
                    status.text = "${est.message}. Drag the dots onto the board's corners."
                } else {
                    editor.setEstimate(c)
                    status.text = if (editor.userEdited)
                        "Auto estimate ready. Tap \"Auto estimate\" to use it."
                    else
                        "Auto-detected. Drag any dot that's off, then confirm."
                }
            }
        }
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val editor = view.findViewById<CornerEditorView>(R.id.editor)
        val path = requireArguments().getString(ARG_PATH)!!
        val appCtx = requireContext().applicationContext

        // Show the photo right away; dots start at the last saved corners (or a default box)
        editor.setImage(ImageUtil.loadUpright(path), Prefs.corners(appCtx))

        // Step 1: ask the computer for its estimate in the background
        runDetect(view, editor, path)

        // Step 2: the human adjusts
        view.findViewById<View>(R.id.btn_auto).setOnClickListener {
            if (editor.hasEstimate) editor.resetCorners() else runDetect(view, editor, path)
        }
        view.findViewById<View>(R.id.btn_rotate).setOnClickListener { editor.rotateLabels() }
        view.findViewById<View>(R.id.btn_retake).setOnClickListener {
            parentFragmentManager.setFragmentResult(RESULT_KEY, Bundle().apply { putBoolean("retake", true) })
            dismiss()
        }
        view.findViewById<View>(R.id.btn_confirm).setOnClickListener {
            Prefs.setCorners(appCtx, editor.corners())
            parentFragmentManager.setFragmentResult(RESULT_KEY, Bundle().apply { putBoolean("confirmed", true) })
            dismiss()
        }
        // Step 3 (refinement) happens on the Mac when the shutter uploads with these corners
    }
}
