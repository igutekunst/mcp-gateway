import { useEffect, useState, useCallback, useMemo } from 'react'
import { LogEntry, LogsFilter, fetchLogs } from '../api/logs'
import { format } from 'date-fns'
import {
    Box,
    Table,
    Thead,
    Tbody,
    Tr,
    Th,
    Td,
    Select,
    Input,
    Button,
    Flex,
    Text,
    Spinner,
    Alert,
    AlertIcon,
    Stack,
    useColorModeValue,
    Tag,
    Collapse,
    Code,
} from '@chakra-ui/react'

interface LogViewerProps {
    appId: number
    refreshInterval?: number // in milliseconds
    initialFilter?: Partial<LogsFilter>
}

const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR'] as const
const ITEMS_PER_PAGE = 50

export function LogViewer({ appId, refreshInterval = 5000, initialFilter = {} }: LogViewerProps) {
    const [logs, setLogs] = useState<LogEntry[]>([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [expandedMetadata, setExpandedMetadata] = useState<number[]>([])

    // Set default time range to last 24 hours if not provided
    const defaultEndTime = new Date().toISOString()
    const defaultStartTime = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()

    const [filter, setFilter] = useState<LogsFilter>({
        limit: ITEMS_PER_PAGE,
        offset: 0,
        start_time: defaultStartTime,
        end_time: defaultEndTime,
        ...initialFilter
    })

    // Toggle metadata visibility
    const toggleMetadata = (logId: number) => {
        setExpandedMetadata(prev => 
            prev.includes(logId)
                ? prev.filter(id => id !== logId)
                : [...prev, logId]
        )
    }

    // Fetch logs with current filter
    const fetchLogsData = useCallback(async () => {
        try {
            setLoading(true)
            setError(null)
            const response = await fetchLogs(appId, filter)
            setLogs(response.logs)
            setTotal(response.total)
        } catch (err) {
            if (err instanceof Error) {
                setError(err.message)
            } else {
                setError('Failed to fetch logs')
            }
            // Clear logs on error to avoid showing stale data
            setLogs([])
            setTotal(0)
        } finally {
            setLoading(false)
        }
    }, [appId, filter])

    // Reset time range to last 24 hours
    const resetTimeRange = () => {
        setFilter(prev => ({
            ...prev,
            start_time: defaultStartTime,
            end_time: defaultEndTime,
            offset: 0
        }))
    }

    // Initial fetch and refresh interval
    useEffect(() => {
        fetchLogsData()
        
        if (refreshInterval > 0) {
            const interval = setInterval(fetchLogsData, refreshInterval)
            return () => clearInterval(interval)
        }
    }, [fetchLogsData, refreshInterval])

    // Memoized unique connection IDs for filtering
    const connectionIds = useMemo(() => {
        const ids = new Set(logs.map(log => log.connection_id).filter(Boolean))
        return Array.from(ids)
    }, [logs])

    // Filter handlers
    const handleLevelChange = (level: string | null) => {
        setFilter(prev => ({
            ...prev,
            level: level as LogEntry['level'] | undefined,
            offset: 0
        }))
    }

    const handleConnectionChange = (connectionId: string | null) => {
        setFilter(prev => ({
            ...prev,
            connection_id: connectionId || undefined,
            offset: 0
        }))
    }

    const handleTimeRangeChange = (startTime: string | null, endTime: string | null) => {
        setFilter(prev => ({
            ...prev,
            // Convert local datetime to UTC for API
            start_time: startTime ? new Date(startTime).toISOString().slice(0, 16) : undefined,
            end_time: endTime ? new Date(endTime).toISOString().slice(0, 16) : undefined,
            offset: 0
        }))
    }

    const handlePageChange = (newOffset: number) => {
        setFilter(prev => ({
            ...prev,
            offset: newOffset
        }))
    }

    // Render log level with appropriate color
    const getLevelColor = (level: LogEntry['level']) => {
        switch (level) {
            case 'DEBUG': return 'gray'
            case 'INFO': return 'blue'
            case 'WARNING': return 'yellow'
            case 'ERROR': return 'red'
            default: return 'gray'
        }
    }

    const bgColor = useColorModeValue('white', 'gray.800')
    const borderColor = useColorModeValue('gray.200', 'gray.700')

    return (
        <Stack spacing={4}>
            {/* Filters */}
            <Box p={4} bg={bgColor} borderRadius="lg" borderWidth="1px" borderColor={borderColor}>
                <Flex wrap="wrap" gap={4} align="center">
                    <Select
                        value={filter.level || ''}
                        onChange={e => handleLevelChange(e.target.value || null)}
                        placeholder="All Levels"
                        w="auto"
                    >
                        {LOG_LEVELS.map(level => (
                            <option key={level} value={level}>{level}</option>
                        ))}
                    </Select>

                    <Select
                        value={filter.connection_id || ''}
                        onChange={e => handleConnectionChange(e.target.value || null)}
                        placeholder="All Connections"
                        w="auto"
                    >
                        {connectionIds.map(id => (
                            <option key={id} value={id}>{id}</option>
                        ))}
                    </Select>

                    <Input
                        type="datetime-local"
                        value={filter.start_time?.slice(0, 16) || ''}
                        onChange={e => handleTimeRangeChange(e.target.value || null, filter.end_time || null)}
                        placeholder="Start Time"
                        w="auto"
                        max={new Date().toISOString().slice(0, 16)}
                    />

                    <Input
                        type="datetime-local"
                        value={filter.end_time?.slice(0, 16) || ''}
                        onChange={e => handleTimeRangeChange(filter.start_time || null, e.target.value || null)}
                        placeholder="End Time"
                        w="auto"
                        max={new Date().toISOString().slice(0, 16)}
                    />

                    <Button
                        size="sm"
                        onClick={resetTimeRange}
                        colorScheme="blue"
                        variant="outline"
                    >
                        Last 24 Hours
                    </Button>
                </Flex>
            </Box>

            {/* Error message */}
            {error && (
                <Alert status="error">
                    <AlertIcon />
                    {error}
                </Alert>
            )}

            {/* Loading state */}
            {loading && (
                <Flex justify="center" p={4}>
                    <Spinner />
                </Flex>
            )}

            {/* Logs table */}
            <Box overflowX="auto" bg={bgColor} borderRadius="lg" borderWidth="1px" borderColor={borderColor}>
                <Table variant="simple">
                    <Thead>
                        <Tr>
                            <Th>Time</Th>
                            <Th>Level</Th>
                            <Th>Message</Th>
                            <Th>Connection</Th>
                        </Tr>
                    </Thead>
                    <Tbody>
                        {logs.map(log => (
                            <Tr key={log.id}>
                                <Td whiteSpace="nowrap">
                                    {format(new Date(log.timestamp), 'yyyy-MM-dd HH:mm:ss')}
                                </Td>
                                <Td>
                                    <Tag colorScheme={getLevelColor(log.level)}>
                                        {log.level}
                                    </Tag>
                                </Td>
                                <Td>
                                    <Text>{log.message}</Text>
                                    {log.log_metadata && (
                                        <Box mt={2}>
                                            <Button 
                                                size="sm" 
                                                variant="outline" 
                                                onClick={() => toggleMetadata(log.id)}
                                            >
                                                {expandedMetadata.includes(log.id) ? 'Hide' : 'Show'} Metadata
                                            </Button>
                                            <Collapse in={expandedMetadata.includes(log.id)}>
                                                <Code mt={2} p={2} borderRadius="md" display="block" whiteSpace="pre">
                                                    {JSON.stringify(log.log_metadata, null, 2)}
                                                </Code>
                                            </Collapse>
                                        </Box>
                                    )}
                                </Td>
                                <Td whiteSpace="nowrap">
                                    {log.connection_id || '-'}
                                </Td>
                            </Tr>
                        ))}
                    </Tbody>
                </Table>
            </Box>

            {/* Pagination */}
            <Flex justify="space-between" align="center" px={4}>
                <Text fontSize="sm" color="gray.600">
                    Showing {Math.min((filter.offset || 0) + 1, total)} to {Math.min((filter.offset || 0) + logs.length, total)} of {total} results
                </Text>
                <Stack direction="row" spacing={2}>
                    <Button
                        onClick={() => handlePageChange(Math.max(0, (filter.offset || 0) - ITEMS_PER_PAGE))}
                        isDisabled={!filter.offset || filter.offset === 0}
                        size="sm"
                    >
                        Previous
                    </Button>
                    <Button
                        onClick={() => handlePageChange((filter.offset || 0) + ITEMS_PER_PAGE)}
                        isDisabled={(filter.offset || 0) + logs.length >= total}
                        size="sm"
                    >
                        Next
                    </Button>
                </Stack>
            </Flex>
        </Stack>
    )
} 