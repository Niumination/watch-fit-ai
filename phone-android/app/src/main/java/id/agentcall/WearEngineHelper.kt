package id.agentcall

import android.content.Context
import android.util.Log

/**
 * Helper untuk komunikasi Wear Engine P2P (HP -> WATCH FIT 5).
 *
 * Menggunakan deteksi kelas runtime (reflection-safe):
 * - Jika library `com.huawei.hms:wearengine` ada di classpath, helper akan
 *   mencari jam Huawei yang terhubung via Huawei Health dan mengirimkan pesan P2P.
 * - Jika belum ditambahkan ke dependencies, helper tidak akan crash (graceful no-op).
 *
 * Paket peer di jam: `id.agentcall.watch`
 */
object WearEngineHelper {

    private const val TAG = "WearEngineHelper"
    private const val WATCH_PKG_NAME = "id.agentcall.watch"

    @Volatile
    private var isAvailable: Boolean? = null

    fun isSdkPresent(): Boolean {
        if (isAvailable == null) {
            isAvailable = try {
                Class.forName("com.huawei.wearengine.HiWear")
                true
            } catch (e: Throwable) {
                false
            }
        }
        return isAvailable == true
    }

    /**
     * Kirim string JSON (maksimal 1 KB per pesan P2P Wear Engine) ke app lite di jam.
     */
    fun sendToWatch(ctx: Context, jsonMessage: String) {
        if (!isSdkPresent()) {
            return
        }

        try {
            // HiWear.getDeviceClient(ctx).bondedDevices
            val hiWearClass = Class.forName("com.huawei.wearengine.HiWear")
            val getDeviceClientMethod = hiWearClass.getMethod("getDeviceClient", Context::class.java)
            val deviceClient = getDeviceClientMethod.invoke(null, ctx)

            val getBondedDevicesMethod = deviceClient.javaClass.getMethod("getBondedDevices")
            val task = getBondedDevicesMethod.invoke(deviceClient)

            // com.huawei.hmf.tasks.Tasks.await(task) atau OnSuccessListener
            val addOnSuccessMethod = task.javaClass.getMethod("addOnSuccessListener", Class.forName("com.huawei.hmf.tasks.OnSuccessListener"))

            val proxyHandler = java.lang.reflect.InvocationHandler { _, method, args ->
                if (method?.name == "onSuccess") {
                    val devices = args?.get(0) as? List<*> ?: emptyList<Any>()
                    if (devices.isNotEmpty()) {
                        val targetDevice = devices[0]
                        sendP2p(ctx, targetDevice, jsonMessage)
                    }
                }
                null
            }

            val listenerClass = Class.forName("com.huawei.hmf.tasks.OnSuccessListener")
            val proxy = java.lang.reflect.Proxy.newProxyInstance(
                listenerClass.classLoader,
                arrayOf(listenerClass),
                proxyHandler
            )
            addOnSuccessMethod.invoke(task, proxy)

        } catch (e: Throwable) {
            Log.w(TAG, "Wear Engine sendToWatch skipped: ${e.message}")
        }
    }

    /**
     * Kirim file (WAV jawaban) ke app lite di jam via Wear Engine file transfer.
     * fileName mis. "jawab.wav" — jam simpan ke internal://app/ + putar via @system.audio.
     */
    fun sendFileToWatch(ctx: Context, bytes: ByteArray, fileName: String) {
        try {
            val hiWearClass = Class.forName("com.huawei.wearengine.HiWear")
            val device = firstBondedDevice(ctx) ?: return
            val getFileClient = hiWearClass.getMethod("getFileClient", Context::class.java)
            val fileClient = getFileClient.invoke(null, ctx)
            val tmp = java.io.File(ctx.cacheDir, fileName)
            tmp.writeBytes(bytes)
            val sendFile = fileClient.javaClass.getMethod(
                "sendFile", Class.forName("com.huawei.wearengine.device.Device"),
                java.io.File::class.java,
                Class.forName("com.huawei.wearengine.p2p.FileSendCallback"))
            val cbClass = Class.forName("com.huawei.wearengine.p2p.FileSendCallback")
            val proxy = java.lang.reflect.Proxy.newProxyInstance(
                cbClass.classLoader, arrayOf(cbClass),
                java.lang.reflect.InvocationHandler { _, _, _ -> null })
            sendFile.invoke(fileClient, device, tmp, proxy)
        } catch (e: Throwable) {
            Log.w(TAG, "sendFileToWatch skipped: ${e.message}")
        }
    }

    private fun firstBondedDevice(ctx: Context): Any? {
        return try {
            val hiWearClass = Class.forName("com.huawei.wearengine.HiWear")
            val deviceClient = hiWearClass.getMethod("getDeviceClient", Context::class.java).invoke(null, ctx)
            val task = deviceClient.javaClass.getMethod("getBondedDevices").invoke(deviceClient)
            var result: Any? = null
            val latch = java.util.concurrent.CountDownLatch(1)
            val listenerClass = Class.forName("com.huawei.hmf.tasks.OnSuccessListener")
            val proxy = java.lang.reflect.Proxy.newProxyInstance(
                listenerClass.classLoader, arrayOf(listenerClass),
                java.lang.reflect.InvocationHandler { _, method, args ->
                    val devices = args?.get(0) as? List<*> ?: emptyList<Any>()
                    if (devices.isNotEmpty()) result = devices[0]
                    latch.countDown()
                    null
                })
            deviceClient.javaClass.getMethod("getBondedDevices")
            task.javaClass.getMethod("addOnSuccessListener", listenerClass).invoke(task, proxy)
            latch.await(5, java.util.concurrent.TimeUnit.SECONDS)
            result
        } catch (e: Throwable) {
            null
        }
    }

    private fun sendP2p(ctx: Context, device: Any?, jsonMessage: String) {
        if (device == null) return
        try {
            val hiWearClass = Class.forName("com.huawei.wearengine.HiWear")
            val getP2pClientMethod = hiWearClass.getMethod("getP2pClient", Context::class.java)
            val p2pClient = getP2pClientMethod.invoke(null, ctx)

            // p2pClient.setPeerPkgName(WATCH_PKG_NAME)
            p2pClient.javaClass.getMethod("setPeerPkgName", String::class.java).invoke(p2pClient, WATCH_PKG_NAME)

            // Message.Builder().setPayload(bytes).build()
            val messageBuilderClass = Class.forName("com.huawei.wearengine.p2p.Message\$Builder")
            val builder = messageBuilderClass.getConstructor().newInstance()
            val setPayloadMethod = messageBuilderClass.getMethod("setPayload", ByteArray::class.java)
            setPayloadMethod.invoke(builder, jsonMessage.toByteArray(Charsets.UTF_8))

            val buildMethod = messageBuilderClass.getMethod("build")
            val messageObj = buildMethod.invoke(builder)

            // p2pClient.send(device, message, sendCallback)
            val sendMethod = p2pClient.javaClass.getMethod(
                "send",
                Class.forName("com.huawei.wearengine.device.Device"),
                Class.forName("com.huawei.wearengine.p2p.Message"),
                Class.forName("com.huawei.wearengine.p2p.SendCallback")
            )

            val callbackClass = Class.forName("com.huawei.wearengine.p2p.SendCallback")
            val cbProxy = java.lang.reflect.Proxy.newProxyInstance(
                callbackClass.classLoader,
                arrayOf(callbackClass),
                java.lang.reflect.InvocationHandler { _, method, args ->
                    if (method?.name == "onSendResult") {
                        Log.d(TAG, "Wear Engine onSendResult: ${args?.get(0)}")
                    }
                    null
                })

            sendMethod.invoke(p2pClient, device, messageObj, cbProxy)
        } catch (e: Throwable) {
            Log.w(TAG, "sendP2p error: ${e.message}")
        }
    }
}
