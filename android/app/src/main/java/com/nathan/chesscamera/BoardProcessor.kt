package com.nathan.chesscamera

import android.content.Context
import java.io.File

data class ProcessResult(val ok: Boolean, val message: String, val fen: String? = null)

/** corners == null means detection failed; message says why. */
data class CornerEstimate(val corners: BoardCorners?, val message: String)

interface BoardProcessor {
    /** Step 1: the computer's first guess at the 4 corners (order a8, h8, h1, a1). */
    fun detectCorners(photo: File, onResult: (CornerEstimate) -> Unit)

    /** Step 3: refine (using the user's corners if given) and read the position. */
    fun process(photo: File, corners: BoardCorners?, onResult: (ProcessResult) -> Unit)
}

object Processors {
    fun get(ctx: Context): BoardProcessor =
        if (Prefs.useLocal(ctx)) LocalProcessor() else RemoteProcessor(Prefs.macIp(ctx))
}
