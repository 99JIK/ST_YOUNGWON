// EvenSquareSum.java
import java.util.stream.IntStream;

public class EvenSquareSum {

    public int calculate(int[] numbers) {
        return IntStream.of(numbers)
                .filter(x -> x % 2 == 0)
                .reduce(0, (x, y) -> x + (y * y));
    }
}