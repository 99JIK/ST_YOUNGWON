// StreamStats.java
import java.util.stream.IntStream;

public class StreamStats {

    public void calculate(int[] numbers) {
        System.out.println("Count: " + IntStream.of(numbers).count());
        System.out.println("Min: " + IntStream.of(numbers).min().getAsInt());
        System.out.println("Max: " + IntStream.of(numbers).max().getAsInt());
        System.out.println("Sum: " + IntStream.of(numbers).sum());
        System.out.printf("Average: %.2f\n", IntStream.of(numbers).average().getAsDouble());
    }
}