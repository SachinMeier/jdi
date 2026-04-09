package com.sachinmeier.jdivoiceandroid.lifx

import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.SocketTimeoutException
import java.util.concurrent.ConcurrentHashMap
import kotlin.random.Random

class LifxLanClient {
    private data class CacheEntry(
        val lights: List<LanLight>,
        val expiresAtMs: Long,
    )

    private val cache = ConcurrentHashMap<Int, CacheEntry>()

    suspend fun listLights(
        timeoutMs: Int,
        cacheTtlMs: Long,
    ): List<LanLight> {
        val now = System.currentTimeMillis()
        cache[timeoutMs]?.takeIf { it.expiresAtMs > now }?.let { return it.lights }
        val lights = discoverLights(timeoutMs)
        cache[timeoutMs] = CacheEntry(lights, now + cacheTtlMs)
        return lights
    }

    suspend fun setPower(
        light: LanLight,
        powerOn: Boolean,
        durationMs: Int,
    ) {
        val packet = LifxPacketCodec.buildSetPower(
            sourceId = Random.nextInt(),
            sequence = Random.nextInt(0, 255),
            targetMac = light.macAddress,
            isOn = powerOn,
            durationMs = durationMs,
        )
        sendUnicast(light.ipAddress, packet)
    }

    suspend fun getPower(light: LanLight): Boolean? {
        val socket = DatagramSocket().apply { soTimeout = 500 }
        socket.use {
            val sourceId = Random.nextInt()
            val sequence = Random.nextInt(0, 255)
            val packet = LifxPacketCodec.buildGetPower(
                sourceId = sourceId,
                sequence = sequence,
                targetMac = light.macAddress,
            )
            socket.send(
                DatagramPacket(
                    packet,
                    packet.size,
                    InetAddress.getByName(light.ipAddress),
                    LifxPacketCodec.PORT,
                )
            )

            val response = receiveMatchingPacket(
                socket = socket,
                expectedMessageType = LifxPacketCodec.MSG_LIGHT_STATE_POWER,
                expectedSourceId = sourceId,
                expectedSequence = sequence,
            ) ?: return null
            return LifxPacketCodec.parseStatePower(response)?.level?.let { it > 0 }
        }
    }

    private fun discoverLights(timeoutMs: Int): List<LanLight> {
        val socket = DatagramSocket().apply {
            broadcast = true
            soTimeout = 200
        }
        socket.use {
            val sourceId = Random.nextInt()
            val sequence = Random.nextInt(0, 255)
            val request = LifxPacketCodec.buildGetService(sourceId, sequence)
            for (address in broadcastAddresses()) {
                socket.send(DatagramPacket(request, request.size, address, LifxPacketCodec.PORT))
            }

            val deadline = System.currentTimeMillis() + timeoutMs
            val servicesByMac = linkedMapOf<String, Pair<String, Int>>()
            while (System.currentTimeMillis() < deadline) {
                val parsed = receiveMatchingPacket(
                    socket = socket,
                    expectedMessageType = LifxPacketCodec.MSG_STATE_SERVICE,
                    expectedSourceId = sourceId,
                    expectedSequence = sequence,
                ) ?: continue
                val stateService = LifxPacketCodec.parseStateService(parsed) ?: continue
                if (stateService.service != 1) {
                    continue
                }
                servicesByMac.putIfAbsent(
                    stateService.macAddress,
                    parsed.remoteAddress.orEmpty() to stateService.port,
                )
            }

            return servicesByMac.entries.mapNotNull { (macAddress, target) ->
                val ipAddress = target.first.ifBlank { null } ?: return@mapNotNull null
                val label = fetchLabel(socket, ipAddress, macAddress) ?: return@mapNotNull null
                LanLight(macAddress = macAddress, ipAddress = ipAddress, label = label)
            }
        }
    }

    private fun fetchLabel(socket: DatagramSocket, ipAddress: String, macAddress: String): String? {
        val sourceId = Random.nextInt()
        val sequence = Random.nextInt(0, 255)
        val request = LifxPacketCodec.buildGetLabel(sourceId, sequence, macAddress)
        socket.send(
            DatagramPacket(
                request,
                request.size,
                InetAddress.getByName(ipAddress),
                LifxPacketCodec.PORT,
            )
        )
        val parsed = receiveMatchingPacket(
            socket = socket,
            expectedMessageType = LifxPacketCodec.MSG_STATE_LABEL,
            expectedSourceId = sourceId,
            expectedSequence = sequence,
        ) ?: return null
        return LifxPacketCodec.parseStateLabel(parsed)?.label
    }

    private fun sendUnicast(ipAddress: String, packet: ByteArray) {
        DatagramSocket().use { socket ->
            socket.send(
                DatagramPacket(
                    packet,
                    packet.size,
                    InetAddress.getByName(ipAddress),
                    LifxPacketCodec.PORT,
                )
            )
        }
    }

    private fun receiveMatchingPacket(
        socket: DatagramSocket,
        expectedMessageType: Int,
        expectedSourceId: Int,
        expectedSequence: Int,
    ): LifxPacketCodec.ParsedPacket? {
        while (true) {
            val buffer = ByteArray(1024)
            val packet = DatagramPacket(buffer, buffer.size)
            try {
                socket.receive(packet)
            } catch (_: SocketTimeoutException) {
                return null
            }
            val parsed = LifxPacketCodec.parse(packet.data.copyOf(packet.length)) ?: continue
            if (parsed.messageType != expectedMessageType) {
                continue
            }
            if (parsed.sourceId != expectedSourceId || parsed.sequence != expectedSequence) {
                continue
            }
            return parsed.copy(
                remoteAddress = packet.address.hostAddress,
            )
        }
    }

    private fun broadcastAddresses(): List<InetAddress> {
        val addresses = mutableListOf<InetAddress>()
        val interfaces = NetworkInterface.getNetworkInterfaces() ?: return listOf(InetAddress.getByName("255.255.255.255"))
        while (interfaces.hasMoreElements()) {
            val networkInterface = interfaces.nextElement()
            if (!networkInterface.isUp || networkInterface.isLoopback) {
                continue
            }
            for (interfaceAddress in networkInterface.interfaceAddresses) {
                val broadcast = interfaceAddress.broadcast ?: continue
                addresses += broadcast
            }
        }
        if (addresses.isEmpty()) {
            addresses += InetAddress.getByName("255.255.255.255")
        }
        return addresses.distinctBy { it.hostAddress }
    }
}
