; Bounded model for the 12 x 900 fractionation scenario.
; Run with: z3 formal/resource_invariant.smt2
; The model asks whether a unit-call filter can authorize every individual call while the
; trajectory violates the 10,000 aggregate invariant. SAT is the expected counterexample.

(set-logic QF_LIA)
(declare-const a1 Int)  (declare-const a2 Int)
(declare-const a3 Int)  (declare-const a4 Int)
(declare-const a5 Int)  (declare-const a6 Int)
(declare-const a7 Int)  (declare-const a8 Int)
(declare-const a9 Int)  (declare-const a10 Int)
(declare-const a11 Int) (declare-const a12 Int)

(assert (= a1 900))  (assert (= a2 900))
(assert (= a3 900))  (assert (= a4 900))
(assert (= a5 900))  (assert (= a6 900))
(assert (= a7 900))  (assert (= a8 900))
(assert (= a9 900))  (assert (= a10 900))
(assert (= a11 900)) (assert (= a12 900))

; Unit-call authorization baseline.
(assert (and (<= a1 10000) (<= a2 10000) (<= a3 10000) (<= a4 10000)))
(assert (and (<= a5 10000) (<= a6 10000) (<= a7 10000) (<= a8 10000)))
(assert (and (<= a9 10000) (<= a10 10000) (<= a11 10000) (<= a12 10000)))

; Global trajectory violation.
(assert (> (+ a1 a2 a3 a4 a5 a6 a7 a8 a9 a10 a11 a12) 10000))
(check-sat)
(get-model)

