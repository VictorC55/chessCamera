package com.nathan.chesscamera

import java.io.File

class LocalProcessor : BoardProcessor {

    override fun detectCorners(photo: File, onResult: (CornerEstimate) -> Unit) {
        // TODO(migration): run the on-device corner model + ECC refinement here
        onResult(CornerEstimate(null, "Auto-detect isn't available on-device yet"))
    }

    override fun process(photo: File, corners: BoardCorners?, onResult: (ProcessResult) -> Unit) {
        // TODO(migration): on-device pipeline goes here.
        //  1. load the TFLite piece model
        //  2. refine `corners` (ECC) -> homography (C++ via JNI)
        //  3. map pieces to squares -> FEN, then ProcessResult(true, "Done", fen)
        onResult(ProcessResult(false, "On-device processing isn't built yet"))
    }
}
