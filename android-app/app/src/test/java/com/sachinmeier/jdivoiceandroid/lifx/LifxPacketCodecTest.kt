package com.sachinmeier.jdivoiceandroid.lifx

import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class LifxPacketCodecTest {
    @Test
    fun parsesStateServicePacket() {
        val packet = makePacket(
            messageType = LifxPacketCodec.MSG_STATE_SERVICE,
            macAddress = "d0:73:d5:89:d3:b7",
            sourceId = 1234,
            sequence = 7,
            payload = ByteBuffer.allocate(5)
                .order(ByteOrder.LITTLE_ENDIAN)
                .put(1)
                .putInt(56_700)
                .array(),
        )

        val parsed = LifxPacketCodec.parse(packet)
        val state = parsed?.let(LifxPacketCodec::parseStateService)

        assertNotNull(state)
        assertEquals("d0:73:d5:89:d3:b7", state?.macAddress)
        assertEquals(1, state?.service)
        assertEquals(56_700, state?.port)
    }

    @Test
    fun parsesStateLabelPacket() {
        val labelPayload = ByteArray(32)
        "Bedroom1".toByteArray().copyInto(labelPayload)
        val packet = makePacket(
            messageType = LifxPacketCodec.MSG_STATE_LABEL,
            macAddress = "d0:73:d5:89:d3:b7",
            sourceId = 1234,
            sequence = 3,
            payload = labelPayload,
        )

        val parsed = LifxPacketCodec.parse(packet)
        val state = parsed?.let(LifxPacketCodec::parseStateLabel)

        assertNotNull(state)
        assertEquals("Bedroom1", state?.label)
    }

    private fun makePacket(
        messageType: Int,
        macAddress: String,
        sourceId: Int,
        sequence: Int,
        payload: ByteArray,
    ): ByteArray {
        val header = ByteBuffer.allocate(36).order(ByteOrder.LITTLE_ENDIAN)
        header.putShort((36 + payload.size).toShort())
        val flags = 1024 or (1 shl 12)
        header.putShort(flags.toShort())
        header.putInt(sourceId)

        val targetBytes = ByteArray(8)
        macAddress.split(":").forEachIndexed { index, value ->
            targetBytes[index] = value.toInt(16).toByte()
        }
        header.put(targetBytes)
        header.put(ByteArray(6))
        header.put(1)
        header.put(sequence.toByte())
        header.putLong(0L)
        header.putShort(messageType.toShort())
        header.putShort(0)
        return header.array() + payload
    }
}
