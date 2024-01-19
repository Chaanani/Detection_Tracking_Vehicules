import math

def intersect(A,B,C,D): 
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
    re1=ccw(A,C,D)
    re2=ccw(B,C,D)    
    re3=ccw(A,B,C)
    re4=ccw(A,B,D)
    return re1 != re2 and re3 != re4
def vector_angle(midpoint, previous_midpoint):
        x = midpoint[0] - previous_midpoint[0]
        y = midpoint[1] - previous_midpoint[1]
        return math.degrees(math.atan2(y, x))
def tlbr_midpoint(box):
        minX, minY, maxX, maxY = box
        midpoint = (int((minX+maxX)/2), int((minY+maxY)/2))
        return midpoint