package com.nathan.chesscamera

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View

class CornerEditorView @JvmOverloads constructor(
    ctx: Context, attrs: AttributeSet? = null
) : View(ctx, attrs) {

    private val dp = resources.displayMetrics.density
    private var bmp: Bitmap? = null
    private val pts = Array(4) { PointF() }                 // bitmap pixel coords
    private val labels = arrayOf("a8", "h8", "h1", "a1")
    private val toView = Matrix()
    private val toBmp = Matrix()
    private var active = -1
    private var grabDx = 0f
    private var grabDy = 0f
    private var estimate: BoardCorners? = null

    /** true once the user has dragged a dot or rotated the labels */
    var userEdited = false
        private set

    val hasEstimate: Boolean get() = estimate != null

    private val orange = 0xFFF46524.toInt()
    private val quadPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = orange; style = Paint.Style.STROKE; strokeWidth = 3 * dp
    }
    private val gridPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0x99FFFFFF.toInt(); style = Paint.Style.STROKE; strokeWidth = 1 * dp
    }
    private val dotFill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = orange }
    private val dotRing = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE; style = Paint.Style.STROKE; strokeWidth = 2.5f * dp
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE; textSize = 16 * dp; isFakeBoldText = true
        setShadowLayer(4 * dp, 0f, 0f, Color.BLACK)
    }
    private val clip = Path()

    // ---------------- public API ----------------

    /** Show the photo. Dots start at `initial` (e.g. last saved corners) or an inset rectangle. */
    fun setImage(bitmap: Bitmap, initial: BoardCorners?) {
        bmp = bitmap
        estimate = null
        userEdited = false
        if (initial != null) applyNormalized(initial) else defaultQuad()
        updateMatrix()
        invalidate()
    }

    /** The computer's guess. Applied immediately unless the user has already started editing. */
    fun setEstimate(c: BoardCorners) {
        estimate = c
        if (!userEdited) applyNormalized(c)
    }

    /** Back to the computer's estimate if there is one, otherwise the default rectangle. */
    fun resetCorners() {
        userEdited = false
        val e = estimate
        if (e != null) applyNormalized(e) else defaultQuad()
    }

    /** Shift which dot carries which label (for when the guessed orientation is rotated). */
    fun rotateLabels() {
        val first = PointF(pts[0].x, pts[0].y)
        for (i in 0..2) pts[i].set(pts[i + 1])
        pts[3].set(first)
        userEdited = true
        invalidate()
    }

    fun corners(): BoardCorners {
        val b = bmp!!
        return BoardCorners(pts.map { PointF(it.x / b.width, it.y / b.height) })
    }

    // ---------------- internals ----------------

    private fun applyNormalized(c: BoardCorners) {
        val b = bmp ?: return
        c.pts.forEachIndexed { i, p -> pts[i].set(p.x * b.width, p.y * b.height) }
        invalidate()
    }

    private fun defaultQuad() {
        val b = bmp ?: return
        val l = b.width * 0.15f; val r = b.width * 0.85f
        val t = b.height * 0.15f; val bt = b.height * 0.85f
        pts[0].set(l, t); pts[1].set(r, t); pts[2].set(r, bt); pts[3].set(l, bt)
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, ow: Int, oh: Int) {
        super.onSizeChanged(w, h, ow, oh); updateMatrix()
    }

    private fun updateMatrix() {
        val b = bmp ?: return
        if (width == 0 || height == 0) return
        val s = minOf(width.toFloat() / b.width, height.toFloat() / b.height)
        toView.reset()
        toView.postScale(s, s)
        toView.postTranslate((width - b.width * s) / 2f, (height - b.height * s) / 2f)
        toView.invert(toBmp)
    }

    private fun viewPt(i: Int): FloatArray =
        floatArrayOf(pts[i].x, pts[i].y).also { toView.mapPoints(it) }

    override fun onTouchEvent(e: MotionEvent): Boolean {
        val b = bmp ?: return false
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                var best = -1; var bestD = 64 * dp
                for (i in 0..3) {
                    val p = viewPt(i)
                    val d = Math.hypot((p[0] - e.x).toDouble(), (p[1] - e.y).toDouble()).toFloat()
                    if (d < bestD) { bestD = d; best = i }
                }
                if (best < 0) return false
                active = best
                userEdited = true
                val p = viewPt(best)
                grabDx = p[0] - e.x; grabDy = p[1] - e.y      // no jump when you grab a dot
                parent?.requestDisallowInterceptTouchEvent(true)
                invalidate()
            }
            MotionEvent.ACTION_MOVE -> if (active >= 0) {
                val p = floatArrayOf(e.x + grabDx, e.y + grabDy)
                toBmp.mapPoints(p)
                pts[active].set(p[0].coerceIn(0f, b.width.toFloat()), p[1].coerceIn(0f, b.height.toFloat()))
                invalidate()
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> { active = -1; invalidate() }
        }
        return true
    }

    override fun onDraw(c: Canvas) {
        val b = bmp ?: return
        c.drawBitmap(b, toView, null)

        val v = FloatArray(8)
        for (i in 0..3) { val p = viewPt(i); v[i * 2] = p[0]; v[i * 2 + 1] = p[1] }

        // 8x8 grid: map the unit grid onto the quad with a perspective transform
        val grid = Matrix()
        if (grid.setPolyToPoly(floatArrayOf(0f, 0f, 8f, 0f, 8f, 8f, 0f, 8f), 0, v, 0, 4)) {
            for (i in 0..8) {
                val a = floatArrayOf(i.toFloat(), 0f, i.toFloat(), 8f); grid.mapPoints(a)
                c.drawLine(a[0], a[1], a[2], a[3], gridPaint)
                val h = floatArrayOf(0f, i.toFloat(), 8f, i.toFloat()); grid.mapPoints(h)
                c.drawLine(h[0], h[1], h[2], h[3], gridPaint)
            }
        }
        for (i in 0..3) {
            val j = (i + 1) % 4
            c.drawLine(v[i * 2], v[i * 2 + 1], v[j * 2], v[j * 2 + 1], quadPaint)
        }
        for (i in 0..3) {
            val r = if (i == active) 16 * dp else 12 * dp
            c.drawCircle(v[i * 2], v[i * 2 + 1], r, dotFill)
            c.drawCircle(v[i * 2], v[i * 2 + 1], r, dotRing)
            c.drawText(labels[i], v[i * 2] + 18 * dp, v[i * 2 + 1] - 18 * dp, textPaint)
        }
        if (active >= 0) drawLoupe(c, b)
    }

    private fun drawLoupe(c: Canvas, b: Bitmap) {
        val r = 60 * dp
        val p = viewPt(active)
        val cx = if (p[0] < width / 2f) width - r - 16 * dp else r + 16 * dp   // opposite side of finger
        val cy = r + 16 * dp
        c.save()
        clip.reset(); clip.addCircle(cx, cy, r, Path.Direction.CW)
        c.clipPath(clip)
        c.drawColor(Color.BLACK)
        val m = Matrix(toView)
        m.postScale(3f, 3f, p[0], p[1])
        m.postTranslate(cx - p[0], cy - p[1])
        c.drawBitmap(b, m, null)
        c.restore()
        c.drawCircle(cx, cy, r, dotRing)
        c.drawLine(cx - 10 * dp, cy, cx + 10 * dp, cy, quadPaint)
        c.drawLine(cx, cy - 10 * dp, cx, cy + 10 * dp, quadPaint)
    }
}
