package com.sachinmeier.jdivoiceandroid.lifx

import java.nio.ByteBuffer
import java.nio.ByteOrder

object LifxPacketCodec {
    const val PORT = 56_700

    const val MSG_GET_SERVICE = 2
    const val MSG_STATE_SERVICE = 3
    const val MSG_GET_LABEL = 23
    const val MSG_STATE_LABEL = 25
    const val MSG_LIGHT_GET_POWER = 116
    const val MSG_LIGHT_SET_POWER = 117
    const val MSG_LIGHT_STATE_POWER = 118

    data class StateService(
        val macAddress: String,
        val service: Int,
        val port: Int,
    )

    data class StateLabel(
        val macAddress: String,
        val label: String,
    )

    data class StatePower(
        val macAddress: String,
        val level: Int,
    )

    data class ParsedPacket(
        val sourceId: Int,
        val sequence: Int,
        val messageType: Int,
        val macAddress: String,
        val payload: ByteArray,
        val remoteAddress: String? = null,
    )

    fun buildGetService(sourceId: Int, sequence: Int): ByteArray {
        return buildPacket(
            sourceId = sourceId,
            sequence = sequence,
            targetMac = BROADCAST_MAC,
            messageType = MSG_GET_SERVICE,
            responseRequested = true,
            payload = ByteArray(0),
        )
    }

    fun buildGetLabel(sourceId: Int, sequence: Int, targetMac: String): ByteArray {
        return buildPacket(
            sourceId = sourceId,
            sequence = sequence,
            targetMac = targetMac,
            messageType = MSG_GET_LABEL,
            responseRequested = true,
            payload = ByteArray(0),
        )
    }

    fun buildGetPower(sourceId: Int, sequence: Int, targetMac: String): ByteArray {
        return buildPacket(
            sourceId = sourceId,
            sequence = sequence,
            targetMac = targetMac,
            messageType = MSG_LIGHT_GET_POWER,
            responseRequested = true,
            payload = ByteArray(0),
        )
    }

    fun buildSetPower(
        sourceId: Int,
        sequence: Int,
        targetMac: String,
        isOn: Boolean,
        durationMs: Int,
    ): ByteArray {
        val payload = ByteBuffer.allocate(6)
            .order(ByteOrder.LITTLE_ENDIAN)
            .putShort(if (isOn) 65_535.toShort() else 0.toShort())
            .putInt(durationMs)
            .array()
        return buildPacket(
            sourceId = sourceId,
            sequence = sequence,
            targetMac = targetMac,
            messageType = MSG_LIGHT_SET_POWER,
            responseRequested = false,
            payload = payload,
        )
    }

    fun parse(rawPacket: ByteArray): ParsedPacket? {
        if (rawPacket.size < HEADER_SIZE) {
            return null
        }
        val buffer = ByteBuffer.wrap(rawPacket).order(ByteOrder.LITTLE_ENDIAN)
        val size = buffer.short.toInt() and 0xffff
        if (size < HEADER_SIZE || size > rawPacket.size) {
            return null
        }
        buffer.short
        val sourceId = buffer.int
        val targetBytes = ByteArray(8)
        buffer.get(targetBytes)
        buffer.position(22)
        buffer.get()
        val sequence = buffer.get().toInt() and 0xff
        buffer.position(32)
        val messageType = buffer.short.toInt() and 0xffff
        buffer.short
        val payload = rawPacket.copyOfRange(HEADER_SIZE, size)
        return ParsedPacket(
            sourceId = sourceId,
            sequence = sequence,
            messageType = messageType,
            macAddress = formatMac(targetBytes.copyOfRange(0, 6)),
            payload = payload,
        )
    }

    fun parseStateService(packet: ParsedPacket): StateService? {
        if (packet.messageType != MSG_STATE_SERVICE || packet.payload.size < 5) {
            return null
        }
        val payload = ByteBuffer.wrap(packet.payload).order(ByteOrder.LITTLE_ENDIAN)
        return StateService(
            macAddress = packet.macAddress,
            service = payload.get().toInt() and 0xff,
            port = payload.int,
        )
    }

    fun parseStateLabel(packet: ParsedPacket): StateLabel? {
        if (packet.messageType != MSG_STATE_LABEL || packet.payload.size < 32) {
            return null
        }
        val label = packet.payload.copyOfRange(0, 32)
            .takeWhile { it != 0.toByte() }
            .toByteArray()
            .toString(Charsets.UTF_8)
        return StateLabel(packet.macAddress, label)
    }

    fun parseStatePower(packet: ParsedPacket): StatePower? {
        if (packet.messageType != MSG_LIGHT_STATE_POWER || packet.payload.size < 2) {
            return null
        }
        val level = ByteBuffer.wrap(packet.payload).order(ByteOrder.LITTLE_ENDIAN).short.toInt() and 0xffff
        return StatePower(packet.macAddress, level)
    }

    private fun buildPacket(
        sourceId: Int,
        sequence: Int,
        targetMac: String,
        messageType: Int,
        responseRequested: Boolean,
        payload: ByteArray,
    ): ByteArray {
        val tagged = targetMac == BROADCAST_MAC
        val header = ByteBuffer.allocate(HEADER_SIZE).order(ByteOrder.LITTLE_ENDIAN)
        header.putShort((HEADER_SIZE + payload.size).toShort())

        val flags = 1024 or (1 shl 12) or (if (tagged) 1 shl 13 else 0)
        header.putShort(flags.toShort())
        header.putInt(sourceId)
        header.put(targetMacToBytes(targetMac))
        header.put(ByteArray(6))
        header.put(if (responseRequested) 1.toByte() else 0.toByte())
        header.put(sequence.toByte())
        header.putLong(0L)
        header.putShort(messageType.toShort())
        header.putShort(0)

        return header.array() + payload
    }

    private fun targetMacToBytes(value: String): ByteArray {
        val bytes = ByteArray(8)
        if (value == BROADCAST_MAC) {
            return bytes
        }
        val parts = value.split(":")
        require(parts.size == 6) { "Expected a 6-byte MAC address." }
        for ((index, part) in parts.withIndex()) {
            bytes[index] = part.toInt(16).toByte()
        }
        return bytes
    }

    private fun formatMac(bytes: ByteArray): String {
        return bytes.joinToString(":") { "%02x".format(it.toInt() and 0xff) }
    }

    private const val HEADER_SIZE = 36
    private const val BROADCAST_MAC = "00:00:00:00:00:00"
}
