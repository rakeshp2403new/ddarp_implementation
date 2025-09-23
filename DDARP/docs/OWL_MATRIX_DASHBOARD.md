# OWL Matrix Dashboard

## Overview

The OWL Matrix Dashboard provides a comprehensive tabular view of One-Way Latency (OWL) measurements between all DDARP nodes in the network. This dashboard displays the latency matrix in a format similar to a routing table, making it easy to understand the network topology and performance characteristics.

## Dashboard Features

### 1. OWL Latency Matrix (Main Panel)
- **Format**: Tabular matrix showing latency between all node pairs
- **Layout**: Rows represent source nodes, columns represent destination nodes
- **Values**: Latency measurements in milliseconds (ms)
- **Color Coding**:
  - Green: Low latency (< 20ms)
  - Yellow: Medium latency (20-50ms)
  - Red: High latency (> 50ms)
- **Self-Latency**: Diagonal shows 0ms (node to itself)

### 2. Active OWL Connections per Node
- **Type**: Pie chart
- **Purpose**: Shows the number of active connections from each source node
- **Use Case**: Monitor connectivity health and identify isolated nodes

### 3. OWL Matrix Statistics
- **Type**: Time series chart
- **Metrics**:
  - Average latency across all connections
  - Minimum latency in the network
  - Maximum latency in the network
- **Purpose**: Track overall network performance trends

### 4. OWL Matrix - Detailed View
- **Type**: Sortable table
- **Features**:
  - Filterable by source/destination nodes
  - Sortable by any column
  - Color-coded latency values
- **Purpose**: Detailed analysis and troubleshooting

## Example Matrix Format

```
OWL Matrix
Node      | Node A | Node B | Node C | Node D
----------|--------|--------|--------|--------
Node A    |   0ms  |  15ms  |  32ms  |  28ms
Node B    |  16ms  |   0ms  |  45ms  |  38ms
Node C    |  33ms  |  44ms  |   0ms  |  22ms
Node D    |  27ms  |  39ms  |  21ms  |   0ms
```

## Data Source

The dashboard uses Prometheus metrics from the DDARP system:
- **Primary Metric**: `ddarp_owl_latency_ms`
- **Labels**:
  - `source_node`: The originating node
  - `dest_node`: The destination node
- **Update Interval**: 5 seconds (real-time)

## Variables

### Source Node Filter
- **Name**: `source_node`
- **Type**: Multi-select dropdown
- **Default**: All nodes
- **Purpose**: Filter the matrix to show only specific source nodes

### Destination Node Filter
- **Name**: `dest_node`
- **Type**: Multi-select dropdown
- **Default**: All nodes
- **Purpose**: Filter the matrix to show only specific destination nodes

## Dashboard Configuration

### Access Information
- **Dashboard UID**: `owl-matrix-table`
- **Title**: "OWL Matrix Table"
- **Tags**: ddarp, owl, latency, matrix
- **Refresh Rate**: 5 seconds
- **Time Range**: Last 5 minutes (for real-time view)

### Links
- Back to DDARP Overview Dashboard
- Link to OWL Deep Dive Dashboard for detailed analysis

## Usage Scenarios

### 1. Network Performance Monitoring
- Monitor real-time latency between all node pairs
- Identify performance bottlenecks or degraded connections
- Track network performance trends over time

### 2. Routing Analysis
- Understand the latency characteristics for routing decisions
- Identify optimal paths between nodes
- Analyze the impact of network topology changes

### 3. Troubleshooting
- Quickly identify high-latency connections
- Compare current vs. historical performance
- Filter specific node pairs for detailed analysis

### 4. Capacity Planning
- Analyze network performance patterns
- Identify nodes that may need additional resources
- Plan for network expansion based on latency patterns

## Installation

The dashboard is automatically provisioned when the DDARP monitoring stack is deployed:

1. Ensure Grafana is running with the DDARP configuration
2. The dashboard will be available at: `/d/owl-matrix-table/owl-matrix-table`
3. Dashboard appears in the "DDARP Dashboards" folder in Grafana

## Troubleshooting

### No Data Displayed
- Verify that the DDARP OWL engine is running and collecting metrics
- Check that Prometheus is scraping the DDARP metrics endpoint
- Ensure the metric `ddarp_owl_latency_ms` exists in Prometheus

### Missing Nodes
- Check that all DDARP nodes are properly configured and running
- Verify that the OWL engine is measuring latency to all expected destinations
- Check Prometheus configuration for complete node discovery

### Incorrect Latency Values
- Verify system time synchronization across all nodes
- Check OWL engine configuration for measurement intervals
- Review network connectivity between nodes

## Related Dashboards

- **DDARP Overview**: High-level system overview
- **OWL Deep Dive**: Detailed latency analysis and trends
- **Network Performance**: Overall network metrics and performance
- **System Health**: Node health and resource utilization