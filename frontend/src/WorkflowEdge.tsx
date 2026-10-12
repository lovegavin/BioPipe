import { memo, useId } from "react";
import { BaseEdge, getBezierPath, Position } from "@xyflow/react";
import type { EdgeProps } from "@xyflow/react";

const ARROW_LENGTH = 8;
const targetOutward: Record<Position, readonly [number, number]> = {
  [Position.Left]: [-1, 0],
  [Position.Right]: [1, 0],
  [Position.Top]: [0, -1],
  [Position.Bottom]: [0, 1],
};

export const WorkflowEdge = memo(function WorkflowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  interactionWidth,
}: EdgeProps) {
  const markerId = `workflow-arrow-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const [outwardX, outwardY] = targetOutward[targetPosition];
  // End the curve at the arrow's base; its tip reaches the original port.
  const [path] = getBezierPath({
    sourceX,
    sourceY,
    targetX: targetX + outwardX * ARROW_LENGTH,
    targetY: targetY + outwardY * ARROW_LENGTH,
    sourcePosition,
    targetPosition,
  });

  return (
    <>
      <defs>
        {/* Local marker shares the edge's hover, selection and theme styles. */}
        <marker
          id={markerId}
          viewBox="-1 -5 10 10"
          refX="0"
          refY="0"
          markerWidth="10"
          markerHeight="10"
          markerUnits="userSpaceOnUse"
          orient="auto"
          overflow="visible"
        >
          <path
            className="workflow-edge-arrow"
            d={`M 0 -3.5 L ${ARROW_LENGTH} 0 L 0 3.5 Z`}
          />
        </marker>
      </defs>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={`url(#${markerId})`}
        interactionWidth={interactionWidth}
      />
    </>
  );
});
